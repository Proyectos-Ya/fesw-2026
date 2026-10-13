"""Dobles y fixtures para pruebas de procesamiento de anexos (plan 233, decisión 4)."""

import hashlib
import json
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from app.application.repositories.attachment_extraction_repository import (
    IAttachmentExtractionRepository,
)
from app.application.repositories.attachment_processing_job_repository import (
    IAttachmentProcessingJobRepository,
)
from app.application.repositories.attachment_processing_status_reader import (
    IAttachmentProcessingStatusReader,
)
from app.application.repositories.gemini_usage_repository import (
    IGeminiUsageRepository,
)
from app.application.repositories.tender_digest_repository import (
    ITenderDigestRepository,
)
from app.application.services.attachment_processing_notifier import (
    IAttachmentProcessingNotifier,
)
from app.application.use_cases.attachment_processing.unit import (
    AttachmentProcessingUnit,
    UnitFactory,
)
from app.domain.entities.attachment_extraction import (
    AttachmentExtraction,
    FuenteDeExtraccion,
)
from app.domain.entities.attachment_file import (
    AttachmentFile,
    AttachmentFileSource,
    AttachmentFileStatus,
    AttachmentTrust,
    AttachmentVisibility,
)
from app.domain.entities.attachment_processing import (
    AttachmentProcessingJob,
    EstadoDeExtraccion,
    ProcessingJobKind,
    ProcessingJobStatus,
    agoto_intentos,
)
from app.domain.entities.tender import Tender
from app.domain.entities.tender_attachment import OfficialAttachment
from app.domain.entities.tender_digest import TenderDigest
from app.domain.errors.attachment_processing_errors import (
    ExtractionAlreadyExists,
)
from tests.unit.application.attachment_fakes import (
    InMemoryTenderAttachmentRepository,
)
from tests.unit.application.attachment_file_fakes import (
    FakeAttachmentStorage,
    InMemoryAttachmentFileRepository,
)
from tests.unit.application.fakes import InMemoryTenderRepository

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "documents"
PDF_PATH = next(FIXTURES_DIR.glob("terminos de referencia*.pdf"))
PDF_BYTES = PDF_PATH.read_bytes()
SHA_PDF = hashlib.sha256(PDF_BYTES).hexdigest()

GEN_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent"
)
USO = {"promptTokenCount": 2580, "candidatesTokenCount": 640, "totalTokenCount": 3220}

EXTRACCION_VALIDA = {
    "presupuesto": {
        "monto_clp": None,
        "incluye_iva": True,
        "monto_texto": "$X.XXX.XXX, impuestos incluidos",
        "citas": [
            {
                "documento": "x.pdf",
                "pagina_u_hoja": "4",
                "cita": "cuyo monto total del será de $X.XXX.XXX, impuestos incluidos",
            }
        ],
    },
    "fecha_cierre_primer_llamado": {
        "fecha": "2026-10-05",
        "hora": "15:00",
        "citas": [
            {
                "documento": "x.pdf",
                "pagina_u_hoja": "1",
                "cita": (
                    "Los siguientes Términos Técnicos de Referencia son de"
                    " carácter general"
                ),
            }
        ],
    },
    "requisitos": [
        {
            "descripcion": (
                "Inscripción vigente del proyectista en el Registro de"
                " Consultores ESVAL"
            ),
            "tipo": "tecnico",
            "obligatorio": True,
            "citas": [
                {
                    "documento": "x.pdf",
                    "pagina_u_hoja": "3",
                    "cita": (
                        "Inscripción Vigente del Proyectista en Registro de"
                        " Consultores ESVAL"
                    ),
                }
            ],
        }
    ],
    "items": [],
    "entregables": [
        {
            "descripcion": "Memoria explicativa y de cálculos",
            "plazo": None,
            "citas": [
                {
                    "documento": "x.pdf",
                    "pagina_u_hoja": "3",
                    "cita": "Memoria explicativa y de cálculos",
                }
            ],
        }
    ],
    "puntos_a_tener_en_cuenta": [
        {
            "descripcion": "No se adjudican ofertas sobre el monto estimado",
            "citas": [
                {
                    "documento": "x.pdf",
                    "pagina_u_hoja": "5",
                    "cita": (
                        "No se enviarán ni adjudicarán ofertas que sobrepasen el"
                        " monto estimado"
                    ),
                }
            ],
        }
    ],
    "resumen_general": {
        "texto": (
            "Consultoría para diseñar la conexión de agua potable y"
            " alcantarillado."
        ),
        "citas": [
            {
                "documento": "x.pdf",
                "pagina_u_hoja": "2",
                "cita": (
                    "La Ilustre Municipalidad de Catemu requiere realizar los"
                    " proyectos de conexión de agua potable y de alcantarillado"
                ),
            }
        ],
    },
    "otras_citas": [],
}

EXTRACCION_SIN_CITAS = {
    **deepcopy(EXTRACCION_VALIDA),
    "requisitos": [
        {
            "descripcion": "Requisito sin citas",
            "tipo": "tecnico",
            "obligatorio": True,
            "citas": [],
        }
    ],
}


def respuesta_gemini(
    data: dict[str, Any], usage: dict[str, Any] = USO
) -> dict[str, Any]:
    return {
        "candidates": [
            {
                "content": {"parts": [{"text": json.dumps(data)}]},
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": usage,
        "modelVersion": "gemini-test-001",
    }


class Reloj:
    def __init__(self, ahora: datetime) -> None:
        self.ahora = ahora

    def __call__(self) -> datetime:
        return self.ahora

    def avanzar(self, td: timedelta) -> None:
        self.ahora += td


class RecordingNotifier(IAttachmentProcessingNotifier):
    def __init__(self) -> None:
        self.avisos: int = 0

    def notify(self) -> None:
        self.avisos += 1


class InMemoryAttachmentProcessingJobRepository(
    IAttachmentProcessingJobRepository
):
    def __init__(
        self,
        *,
        files: InMemoryAttachmentFileRepository | None = None,
        extractions: IAttachmentExtractionRepository | None = None,
    ) -> None:
        self.filas: dict[UUID, AttachmentProcessingJob] = {}
        self.files = files
        self.extractions = extractions

    async def enqueue_extract(
        self,
        *,
        attachment_file_id: UUID,
        tender_id: UUID,
        priority: int,
        now: datetime,
    ) -> bool:
        for j in self.filas.values():
            if (
                j.kind == ProcessingJobKind.EXTRACT
                and j.attachment_file_id == attachment_file_id
                and j.status
                in (ProcessingJobStatus.PENDING, ProcessingJobStatus.RUNNING)
            ):
                return False
        job = AttachmentProcessingJob(
            id=uuid4(),
            kind=ProcessingJobKind.EXTRACT,
            status=ProcessingJobStatus.PENDING,
            priority=priority,
            attempts=0,
            last_error=None,
            not_before=now,
            locked_at=None,
            attachment_file_id=attachment_file_id,
            tender_id=tender_id,
            workspace_id=None,
            created_at=now,
            updated_at=now,
        )
        self.filas[job.id] = job
        return True

    async def enqueue_digest(
        self,
        *,
        tender_id: UUID,
        workspace_id: UUID | None,
        priority: int,
        now: datetime,
    ) -> bool:
        for j in self.filas.values():
            if (
                j.kind == ProcessingJobKind.DIGEST
                and j.tender_id == tender_id
                and j.workspace_id == workspace_id
                and j.status
                in (ProcessingJobStatus.PENDING, ProcessingJobStatus.RUNNING)
            ):
                return False
        job = AttachmentProcessingJob(
            id=uuid4(),
            kind=ProcessingJobKind.DIGEST,
            status=ProcessingJobStatus.PENDING,
            priority=priority,
            attempts=0,
            last_error=None,
            not_before=now,
            locked_at=None,
            attachment_file_id=None,
            tender_id=tender_id,
            workspace_id=workspace_id,
            created_at=now,
            updated_at=now,
        )
        self.filas[job.id] = job
        return True

    async def claim_next(
        self, *, now: datetime, kinds: Sequence[ProcessingJobKind]
    ) -> AttachmentProcessingJob | None:
        candidatos = [
            j
            for j in self.filas.values()
            if j.status == ProcessingJobStatus.PENDING
            and j.kind in kinds
            and j.not_before <= now
        ]
        if not candidatos:
            return None
        candidatos.sort(key=lambda j: (-j.priority, j.not_before, j.created_at))
        elegido = candidatos[0]
        actualizado = elegido.model_copy(
            update={
                "status": ProcessingJobStatus.RUNNING,
                "attempts": elegido.attempts + 1,
                "locked_at": now,
                "updated_at": now,
            }
        )
        self.filas[elegido.id] = actualizado
        return actualizado

    async def complete(self, job_id: UUID, *, now: datetime) -> None:
        job = self.filas[job_id]
        self.filas[job_id] = job.model_copy(
            update={
                "status": ProcessingJobStatus.DONE,
                "locked_at": None,
                "updated_at": now,
            }
        )

    def _tiene_gemelo_pendiente(self, job: AttachmentProcessingJob) -> bool:
        for other in self.filas.values():
            if other.id != job.id and other.status == ProcessingJobStatus.PENDING:
                if (
                    job.kind == ProcessingJobKind.EXTRACT
                    and other.kind == ProcessingJobKind.EXTRACT
                    and other.attachment_file_id == job.attachment_file_id
                ):
                    return True
                if (
                    job.kind == ProcessingJobKind.DIGEST
                    and other.kind == ProcessingJobKind.DIGEST
                    and other.tender_id == job.tender_id
                    and other.workspace_id == job.workspace_id
                ):
                    return True
        return False

    async def retry(
        self, job_id: UUID, *, not_before: datetime, error: str, now: datetime
    ) -> None:
        job = self.filas[job_id]
        if self._tiene_gemelo_pendiente(job):
            self.filas[job_id] = job.model_copy(
                update={
                    "status": ProcessingJobStatus.DONE,
                    "last_error": "reemplazado por otro pendiente",
                    "locked_at": None,
                    "updated_at": now,
                }
            )
        else:
            self.filas[job_id] = job.model_copy(
                update={
                    "status": ProcessingJobStatus.PENDING,
                    "not_before": not_before,
                    "last_error": error,
                    "locked_at": None,
                    "updated_at": now,
                }
            )

    async def defer(
        self, job_id: UUID, *, not_before: datetime, reason: str, now: datetime
    ) -> None:
        job = self.filas[job_id]
        intentos = max(0, job.attempts - 1)
        if self._tiene_gemelo_pendiente(job):
            self.filas[job_id] = job.model_copy(
                update={
                    "status": ProcessingJobStatus.DONE,
                    "attempts": intentos,
                    "last_error": "reemplazado por otro pendiente",
                    "locked_at": None,
                    "updated_at": now,
                }
            )
        else:
            self.filas[job_id] = job.model_copy(
                update={
                    "status": ProcessingJobStatus.PENDING,
                    "attempts": intentos,
                    "not_before": not_before,
                    "last_error": reason,
                    "locked_at": None,
                    "updated_at": now,
                }
            )

    async def fail(self, job_id: UUID, *, error: str, now: datetime) -> None:
        job = self.filas[job_id]
        self.filas[job_id] = job.model_copy(
            update={
                "status": ProcessingJobStatus.FAILED,
                "last_error": error,
                "locked_at": None,
                "updated_at": now,
            }
        )

    async def recover_stale(
        self, *, locked_before: datetime, now: datetime
    ) -> int:
        recuperados = 0
        for j in list(self.filas.values()):
            if (
                j.status == ProcessingJobStatus.RUNNING
                and j.locked_at is not None
                and j.locked_at < locked_before
            ):
                if agoto_intentos(j):
                    self.filas[j.id] = j.model_copy(
                        update={
                            "status": ProcessingJobStatus.FAILED,
                            "last_error": (
                                "agotó intentos tras trabajo colgado"
                            ),
                            "locked_at": None,
                            "updated_at": now,
                        }
                    )
                else:
                    self.filas[j.id] = j.model_copy(
                        update={
                            "status": ProcessingJobStatus.PENDING,
                            "locked_at": None,
                            "not_before": now,
                            "updated_at": now,
                        }
                    )
                recuperados += 1
        return recuperados

    async def files_missing_extraction(
        self, *, prompt_version: str, limit: int
    ) -> list[tuple[UUID, UUID]]:
        if self.files is None:
            return []
        faltantes: list[tuple[UUID, UUID]] = []
        for f in self.files.filas.values():
            if f.status != AttachmentFileStatus.STORED:
                continue
            if self.extractions is not None:
                tiene_ext = (
                    await self.extractions.get_for_file(
                        f.id, prompt_version=prompt_version
                    )
                    is not None
                )
                if tiene_ext:
                    continue
            tiene_trabajo = any(
                j.attachment_file_id == f.id
                and j.kind == ProcessingJobKind.EXTRACT
                and j.status
                in (ProcessingJobStatus.PENDING, ProcessingJobStatus.RUNNING)
                for j in self.filas.values()
            )
            if tiene_trabajo:
                continue
            faltantes.append((f.id, f.tender_id))
            if len(faltantes) >= limit:
                break
        return faltantes

    async def purge_finished(self, *, before: datetime) -> int:
        purgados = 0
        for j in list(self.filas.values()):
            if (
                j.status == ProcessingJobStatus.DONE
                and j.updated_at < before
            ):
                del self.filas[j.id]
                purgados += 1
        return purgados


class InMemoryAttachmentExtractionRepository(IAttachmentExtractionRepository):
    def __init__(
        self,
        *,
        files: InMemoryAttachmentFileRepository | None = None,
        attachments: InMemoryTenderAttachmentRepository | None = None,
    ) -> None:
        self.filas: dict[UUID, AttachmentExtraction] = {}
        self.files = files
        self.attachments = attachments

    async def get_for_file(
        self, attachment_file_id: UUID, *, prompt_version: str
    ) -> AttachmentExtraction | None:
        for ext in self.filas.values():
            if (
                ext.attachment_file_id == attachment_file_id
                and ext.prompt_version == prompt_version
            ):
                return ext
        return None

    async def find_reusable(
        self,
        *,
        tender_attachment_id: UUID,
        sha256: str,
        prompt_version: str,
        excluding_file_id: UUID,
    ) -> AttachmentExtraction | None:
        for ext in self.filas.values():
            if (
                ext.attachment_file_id == excluding_file_id
                or ext.prompt_version != prompt_version
            ):
                continue
            if self.files is not None:
                archivo = self.files.filas.get(ext.attachment_file_id)
                if (
                    archivo
                    and archivo.tender_attachment_id == tender_attachment_id
                    and archivo.sha256 == sha256
                    and archivo.status == AttachmentFileStatus.STORED
                ):
                    return ext
        return None

    async def create(
        self, extraction: AttachmentExtraction
    ) -> AttachmentExtraction:
        for ext in self.filas.values():
            if (
                ext.attachment_file_id == extraction.attachment_file_id
                and ext.prompt_version == extraction.prompt_version
            ):
                raise ExtractionAlreadyExists(
                    f"Ya existe extracción para archivo {extraction.attachment_file_id}"
                )
        self.filas[extraction.id] = extraction
        return extraction

    async def list_sources(
        self,
        *,
        tender_id: UUID,
        workspace_id: UUID | None,
        prompt_version: str,
    ) -> list[FuenteDeExtraccion]:
        if self.attachments is None or self.files is None:
            return []
        anexos = {
            a.id: a
            for a in self.attachments.filas.values()
            if a.tender_id == tender_id and a.removed_at is None
        }
        fuentes: list[FuenteDeExtraccion] = []
        for f in self.files.filas.values():
            if f.tender_attachment_id not in anexos:
                continue
            if f.status != AttachmentFileStatus.STORED:
                continue
            if f.visibility == AttachmentVisibility.SHARED:
                if f.trust in (
                    AttachmentTrust.CONFLICT,
                    AttachmentTrust.REJECTED,
                ):
                    continue
            elif f.visibility == AttachmentVisibility.PRIVATE:
                if workspace_id is None or f.workspace_id != workspace_id:
                    continue
            else:
                continue

            ext = await self.get_for_file(f.id, prompt_version=prompt_version)
            if ext is None:
                continue

            anexo = anexos[f.tender_attachment_id]
            fuentes.append(
                FuenteDeExtraccion(
                    extraction_id=ext.id,
                    attachment_file_id=f.id,
                    tender_attachment_id=f.tender_attachment_id,
                    mp_document_id=anexo.mp_document_id,
                    documento=anexo.name,
                    sha256=f.sha256,
                    visibility=f.visibility,
                    trust=f.trust,
                    workspace_id=f.workspace_id,
                    data=ext.data,
                    citas_total=ext.citas_total,
                    citas_verificadas=ext.citas_verificadas,
                    texto_disponible=ext.texto_disponible,
                    model=ext.model,
                    prompt_version=ext.prompt_version,
                    created_at=ext.created_at,
                )
            )
        return fuentes


class InMemoryTenderDigestRepository(ITenderDigestRepository):
    def __init__(self) -> None:
        self.filas: dict[UUID, TenderDigest] = {}

    async def get_current(
        self, tender_id: UUID, workspace_id: UUID | None
    ) -> TenderDigest | None:
        for d in self.filas.values():
            if (
                d.tender_id == tender_id
                and d.workspace_id == workspace_id
                and d.is_current
            ):
                return d
        return None

    async def replace_current(
        self, digest: TenderDigest, *, previous_id: UUID | None
    ) -> TenderDigest:
        if previous_id and previous_id in self.filas:
            self.filas[previous_id] = self.filas[previous_id].model_copy(
                update={"is_current": False}
            )
        for k, d in list(self.filas.items()):
            if (
                d.tender_id == digest.tender_id
                and d.workspace_id == digest.workspace_id
                and d.is_current
            ):
                self.filas[k] = d.model_copy(update={"is_current": False})
        self.filas[digest.id] = digest
        return digest

    async def retire_current(self, tender_id: UUID, workspace_id: UUID) -> None:
        for k, d in list(self.filas.items()):
            if (
                d.tender_id == tender_id
                and d.workspace_id == workspace_id
                and d.is_current
            ):
                self.filas[k] = d.model_copy(update={"is_current": False})

    async def workspaces_with_current(self, tender_id: UUID) -> list[UUID]:
        return [
            d.workspace_id
            for d in self.filas.values()
            if d.tender_id == tender_id
            and d.is_current
            and d.workspace_id is not None
        ]


class InMemoryGeminiUsageRepository(IGeminiUsageRepository):
    def __init__(self) -> None:
        self.reservas: dict[date, int] = {}
        self.tokens: dict[date, tuple[int, int]] = {}

    async def try_reserve_call(self, *, day: date, limit: int) -> bool:
        if limit <= 0:
            return False
        cur = self.reservas.get(day, 0)
        if cur >= limit:
            return False
        self.reservas[day] = cur + 1
        return True

    async def add_tokens(
        self, *, day: date, prompt_tokens: int, output_tokens: int
    ) -> None:
        p, o = self.tokens.get(day, (0, 0))
        self.tokens[day] = (p + prompt_tokens, o + output_tokens)

    async def calls_on(self, day: date) -> int:
        return self.reservas.get(day, 0)


class InMemoryAttachmentProcessingStatusReader(
    IAttachmentProcessingStatusReader
):
    def __init__(
        self,
        jobs: InMemoryAttachmentProcessingJobRepository,
        extractions: InMemoryAttachmentExtractionRepository,
    ) -> None:
        self.jobs = jobs
        self.extractions = extractions

    async def extraction_states(
        self, file_ids: Sequence[UUID], *, prompt_version: str
    ) -> dict[UUID, EstadoDeExtraccion]:
        res: dict[UUID, EstadoDeExtraccion] = {}
        for fid in file_ids:
            extraida = any(
                e.attachment_file_id == fid
                and e.prompt_version == prompt_version
                for e in self.extractions.filas.values()
            )
            trabajos = [
                j
                for j in self.jobs.filas.values()
                if j.attachment_file_id == fid
                and j.kind == ProcessingJobKind.EXTRACT
            ]
            trabajos.sort(key=lambda j: j.created_at)
            hay_en_curso = any(
                j.status
                in (ProcessingJobStatus.PENDING, ProcessingJobStatus.RUNNING)
                for j in trabajos
            )
            ultimo_fallido = bool(
                trabajos and trabajos[-1].status == ProcessingJobStatus.FAILED
            )
            fallida = ultimo_fallido and not hay_en_curso
            res[fid] = EstadoDeExtraccion(extraida=extraida, fallida=fallida)
        return res

    async def pending_count(
        self, *, tender_id: UUID, workspace_id: UUID | None, prompt_version: str
    ) -> int:
        count = 0
        for j in self.jobs.filas.values():
            if j.tender_id != tender_id:
                continue
            if j.status not in (
                ProcessingJobStatus.PENDING,
                ProcessingJobStatus.RUNNING,
            ):
                continue
            if j.kind == ProcessingJobKind.EXTRACT:
                count += 1
            elif (
                j.kind == ProcessingJobKind.DIGEST
                and j.workspace_id == workspace_id
            ):
                count += 1
        return count


class _UnitContextManager:
    def __init__(self, unit: AttachmentProcessingUnit) -> None:
        self.unit = unit
        self.aperturas = 0
        self.abierta = False

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[AttachmentProcessingUnit]:
        self.aperturas += 1
        self.abierta = True
        try:
            yield self.unit
        finally:
            self.abierta = False


def unidades(unit: AttachmentProcessingUnit) -> _UnitContextManager:
    return _UnitContextManager(unit)


@dataclass
class MundoDeProcesamiento:
    tender: Tender
    anexo_pdf: OfficialAttachment
    anexo_docx: OfficialAttachment
    archivo: AttachmentFile
    ws_a: UUID
    ws_b: UUID
    files: InMemoryAttachmentFileRepository
    attachments: InMemoryTenderAttachmentRepository
    tenders: InMemoryTenderRepository
    extractions: InMemoryAttachmentExtractionRepository
    digests: InMemoryTenderDigestRepository
    jobs: InMemoryAttachmentProcessingJobRepository
    usage: IGeminiUsageRepository
    status_reader: InMemoryAttachmentProcessingStatusReader
    notifier: RecordingNotifier
    storage: FakeAttachmentStorage
    unit: AttachmentProcessingUnit
    units: _UnitContextManager


def mundo(
    ahora: datetime = datetime(2026, 10, 3, 15, 0),
) -> MundoDeProcesamiento:
    tender = Tender(
        code="1057539-228-COT26",
        name="Reparación de techumbre",
        status_id=1,
        status_code="publicada",
        published_at=datetime(2026, 9, 28, 13, 0),
        closing_at=datetime(2026, 10, 4, 18, 0),
        call_number=1,
        first_call_closing_at=datetime(2026, 10, 4, 18, 0),
        second_call_closing_at=datetime(2026, 10, 8, 18, 0),
        last_change_at=datetime(2026, 9, 28, 13, 0),
        buyer_rut="1-9",
        buyer_unit="U",
        available_amount_clp=5_000_000,
    )
    ws_a = uuid4()
    ws_b = uuid4()

    anexo_pdf = OfficialAttachment(
        id=uuid4(),
        tender_id=tender.id,
        mp_document_id=1931003,
        name="Bases.pdf",
        name_normalized="bases.pdf",
        ext="pdf",
        first_seen_at=ahora,
        last_seen_at=ahora,
    )
    anexo_docx = OfficialAttachment(
        id=uuid4(),
        tender_id=tender.id,
        mp_document_id=1931004,
        name="Anexo 3.docx",
        name_normalized="anexo 3.docx",
        ext="docx",
        first_seen_at=ahora,
        last_seen_at=ahora,
    )

    archivo = AttachmentFile(
        id=uuid4(),
        tender_attachment_id=anexo_pdf.id,
        tender_id=tender.id,
        sha256=SHA_PDF,
        size_bytes=len(PDF_BYTES),
        storage_key=f"private/{ws_a}/{SHA_PDF}.pdf",
        source=AttachmentFileSource.MANUAL,
        uploader_user_id=uuid4(),
        workspace_id=ws_a,
        visibility=AttachmentVisibility.PRIVATE,
        trust=AttachmentTrust.PENDING,
        status=AttachmentFileStatus.STORED,
        created_at=ahora,
        completed_at=ahora,
    )

    storage = FakeAttachmentStorage()
    storage.subir(archivo.storage_key, PDF_BYTES)

    files = InMemoryAttachmentFileRepository()
    files.filas[archivo.id] = archivo

    attachments = InMemoryTenderAttachmentRepository(
        licitaciones={"1057539-228-COT26": tender.id}
    )
    attachments.filas[(tender.id, anexo_pdf.mp_document_id)] = anexo_pdf
    attachments.filas[(tender.id, anexo_docx.mp_document_id)] = anexo_docx

    tenders = InMemoryTenderRepository()
    tenders.tenders[tender.id] = tender
    extractions = InMemoryAttachmentExtractionRepository(
        files=files, attachments=attachments
    )
    digests = InMemoryTenderDigestRepository()
    jobs = InMemoryAttachmentProcessingJobRepository(
        files=files, extractions=extractions
    )
    usage = InMemoryGeminiUsageRepository()
    status_reader = InMemoryAttachmentProcessingStatusReader(
        jobs=jobs, extractions=extractions
    )
    notifier = RecordingNotifier()

    unit = AttachmentProcessingUnit(
        files=files,
        attachments=attachments,
        tenders=tenders,
        extractions=extractions,
        digests=digests,
        jobs=jobs,
        usage=usage,
    )
    factory = unidades(unit)

    return MundoDeProcesamiento(
        tender=tender,
        anexo_pdf=anexo_pdf,
        anexo_docx=anexo_docx,
        archivo=archivo,
        ws_a=ws_a,
        ws_b=ws_b,
        files=files,
        attachments=attachments,
        tenders=tenders,
        extractions=extractions,
        digests=digests,
        jobs=jobs,
        usage=usage,
        status_reader=status_reader,
        notifier=notifier,
        storage=storage,
        unit=unit,
        units=factory,
    )
