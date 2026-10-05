"""Caso de uso de extracción de datos de un anexo con Gemini (plan 233, decisión 4)."""

import asyncio
import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.application.services.attachment_content_reader import (
    IAttachmentContentReader,
)
from app.application.services.attachment_extraction_ai_service import (
    ExtractionDocument,
    IAttachmentExtractionAIService,
)
from app.application.services.attachment_storage import (
    AttachmentStorageError,
    IAttachmentStorage,
)
from app.application.use_cases.attachment_processing.unit import UnitFactory
from app.domain.entities.attachment_extraction import (
    EXTRACTION_PROMPT_VERSION,
    AttachmentExtraction,
    ExtractionInputMode,
)
from app.domain.entities.attachment_file import (
    AttachmentFile,
    AttachmentFileStatus,
)
from app.domain.entities.attachment_processing import MotivoDeEstado
from app.domain.entities.tender import Tender
from app.domain.errors.attachment_processing_errors import (
    AttachmentExtractionUnavailable,
    ExtractionAlreadyExists,
)
from app.domain.errors.tender_errors import TenderNotFound
from app.domain.services.attachment_file_signatures import (
    FormatoLegible,
    Veredicto,
)
from app.domain.services.citation_verification import (
    IndiceDeTexto,
    verificar_extraccion,
)
from app.domain.services.gemini_budget import (
    dia_del_tope,
    reanudar_tope_en,
)
from app.shared.datetime_utils import utc_now_naive

logger = logging.getLogger(__name__)


async def _get_tender(tenders: ITenderRepository, tender_id: UUID) -> Tender:
    encontradas = await tenders.get_tenders(TenderFilters(ids=[tender_id]))
    if not encontradas:
        raise TenderNotFound(tender_id)
    return encontradas[0]


@dataclass(frozen=True)
class ExtractionOutcome:
    kind: Literal[
        "saved",
        "reused",
        "already_done",
        "skipped",
        "rejected",
        "unsupported",
        "deferred_budget",
    ]
    file: AttachmentFile | None = None
    extraction: AttachmentExtraction | None = None
    reason: MotivoDeEstado | None = None
    not_before: datetime | None = None


class ExtractAttachmentUseCase:
    def __init__(
        self,
        *,
        units: UnitFactory,
        storage: IAttachmentStorage,
        reader: IAttachmentContentReader,
        ai: IAttachmentExtractionAIService,
        daily_budget: int,
        prompt_version: str = EXTRACTION_PROMPT_VERSION,
        clock: Callable[[], datetime] = utc_now_naive,
        new_id: Callable[[], UUID] = uuid4,
    ) -> None:
        self._units = units
        self._storage = storage
        self._reader = reader
        self._ai = ai
        self._daily_budget = daily_budget
        self._prompt_version = prompt_version
        self._clock = clock
        self._new_id = new_id

    async def execute(self, file_id: UUID) -> ExtractionOutcome:
        # 1. Unidad A
        async with self._units() as u:
            archivo = await u.files.get(file_id)
            if archivo is None or archivo.status != AttachmentFileStatus.STORED:
                return ExtractionOutcome("skipped", file=archivo)

            if (
                await u.extractions.get_for_file(
                    archivo.id, prompt_version=self._prompt_version
                )
                is not None
            ):
                return ExtractionOutcome("already_done", file=archivo)

            anexo = await u.attachments.get_attachment(
                archivo.tender_attachment_id
            )
            if anexo is None:
                return ExtractionOutcome("skipped", file=archivo)

            tender = await _get_tender(u.tenders, archivo.tender_id)
            previa = await u.extractions.find_reusable(
                tender_attachment_id=archivo.tender_attachment_id,
                sha256=archivo.sha256,
                prompt_version=self._prompt_version,
                excluding_file_id=archivo.id,
            )

        # 2. Sin sesión: descargar bytes
        try:
            datos = await self._storage.get_bytes(archivo.storage_key)
        except AttachmentStorageError as err:
            raise AttachmentExtractionUnavailable(
                f"almacenamiento: {err}"
            ) from err

        # 3. Checksum
        sha_calculado = await asyncio.to_thread(
            lambda b: hashlib.sha256(b).hexdigest(), datos
        )
        if sha_calculado != archivo.sha256:
            return await self._rechazar(
                archivo, MotivoDeEstado.CHECKSUM_MISMATCH
            )

        # 4. Inspección de magic bytes
        inspeccion = await self._reader.inspect(datos, anexo.ext)
        if inspeccion.veredicto == Veredicto.RECHAZADO:
            return await self._rechazar(
                archivo,
                inspeccion.motivo or MotivoDeEstado.CONTENT_MISMATCH,
            )
        if inspeccion.veredicto == Veredicto.NO_SOPORTADO:
            return await self._no_soportado(
                archivo,
                inspeccion.motivo or MotivoDeEstado.FORMAT_NOT_SUPPORTED,
            )

        # 5. Reusar si existe extracción previa del mismo anexo y sha
        if previa is not None:
            return await self._reusar(archivo, previa)

        # 6. Lectura de texto
        texto = await self._reader.read_text(
            datos, inspeccion.formato, nombre=anexo.name
        )
        if (
            inspeccion.formato in (FormatoLegible.DOCX, FormatoLegible.XLSX)
            and not texto.disponible
        ):
            return await self._no_soportado(archivo, MotivoDeEstado.NO_TEXT)

        # 7. Documento para IA
        documento = ExtractionDocument(
            name=anexo.name,
            sha256=archivo.sha256,
            tender_code=tender.code,
            tender_name=tender.name,
            mime=inspeccion.mime,
            data=(
                datos
                if inspeccion.formato
                in (FormatoLegible.PDF, FormatoLegible.IMAGEN)
                else None
            ),
            text=texto.para_modelo,
            pages=texto.paginas,
        )

        # 8. Tope diario de Gemini (Unidad B)
        ahora = self._clock()
        dia = dia_del_tope(ahora)
        if self._daily_budget <= 0:
            return ExtractionOutcome(
                "deferred_budget",
                file=archivo,
                not_before=reanudar_tope_en(ahora),
            )

        async with self._units() as u:
            if not await u.usage.try_reserve_call(
                day=dia, limit=self._daily_budget
            ):
                return ExtractionOutcome(
                    "deferred_budget",
                    file=archivo,
                    not_before=reanudar_tope_en(ahora),
                )

        # 9. Inferencia con IA
        resultado = await self._ai.extract(documento)
        del datos, documento

        # 10. Verificación de citas
        indice = (
            IndiceDeTexto.desde_secciones([s.texto for s in texto.secciones])
            if texto.disponible
            else None
        )
        data = await asyncio.to_thread(
            verificar_extraccion,
            resultado.data.con_documento(anexo.name),
            indice,
        )

        # 11. Unidad C: guardar extracción y tokens
        citas = list(data.todas_las_citas())
        citas_total = len(citas)
        citas_verificadas = sum(1 for c in citas if c.verificada is True)

        async with self._units() as u:
            prompt_tokens = int(
                resultado.usage_metadata.get("promptTokenCount") or 0
            )
            output_tokens = int(
                resultado.usage_metadata.get("candidatesTokenCount") or 0
            )
            try:
                await u.usage.add_tokens(
                    day=dia,
                    prompt_tokens=prompt_tokens,
                    output_tokens=output_tokens,
                )
            except Exception as exc:
                logger.warning(
                    "Fallo al registrar tokens de uso de Gemini: %s", exc
                )

            extraccion = AttachmentExtraction(
                id=self._new_id(),
                attachment_file_id=archivo.id,
                tender_attachment_id=archivo.tender_attachment_id,
                tender_id=archivo.tender_id,
                sha256=archivo.sha256,
                prompt_version=self._prompt_version,
                model=resultado.model,
                input_mode=resultado.input_mode,
                reused_from_id=None,
                usage_metadata=resultado.usage_metadata,
                citas_total=citas_total,
                citas_verificadas=citas_verificadas,
                texto_disponible=texto.disponible,
                data=data,
                created_at=ahora,
            )
            try:
                guardada = await u.extractions.create(extraccion)
            except ExtractionAlreadyExists:
                return ExtractionOutcome("already_done", file=archivo)

        # 12. Devuelve saved
        return ExtractionOutcome(
            "saved", file=archivo, extraction=guardada
        )

    async def _reusar(
        self, archivo: AttachmentFile, previa: AttachmentExtraction
    ) -> ExtractionOutcome:
        ahora = self._clock()
        reusada = AttachmentExtraction(
            id=self._new_id(),
            attachment_file_id=archivo.id,
            tender_attachment_id=archivo.tender_attachment_id,
            tender_id=archivo.tender_id,
            sha256=archivo.sha256,
            prompt_version=self._prompt_version,
            model=previa.model,
            input_mode=ExtractionInputMode.REUSED,
            reused_from_id=previa.id,
            usage_metadata=None,
            citas_total=previa.citas_total,
            citas_verificadas=previa.citas_verificadas,
            texto_disponible=previa.texto_disponible,
            data=previa.data,
            created_at=ahora,
        )
        async with self._units() as u:
            try:
                guardada = await u.extractions.create(reusada)
            except ExtractionAlreadyExists:
                return ExtractionOutcome("already_done", file=archivo)
        return ExtractionOutcome(
            "reused", file=archivo, extraction=guardada
        )

    async def _rechazar(
        self, archivo: AttachmentFile, motivo: MotivoDeEstado
    ) -> ExtractionOutcome:
        ahora = self._clock()
        async with self._units() as u:
            otras = await u.files.count_other_references(
                storage_key=archivo.storage_key, excluding_id=archivo.id
            )
        if otras == 0:
            try:
                await self._storage.delete(archivo.storage_key)
            except Exception as exc:
                logger.warning(
                    "No se pudo borrar objeto huérfano %s al rechazar: %s",
                    archivo.storage_key,
                    exc,
                )
        actualizado = archivo.como_rechazado(ahora=ahora, motivo=motivo.value)
        async with self._units() as u:
            await u.files.update(actualizado)
        return ExtractionOutcome("rejected", file=actualizado, reason=motivo)

    async def _no_soportado(
        self, archivo: AttachmentFile, motivo: MotivoDeEstado
    ) -> ExtractionOutcome:
        ahora = self._clock()
        actualizado = archivo.como_no_soportado(
            motivo=motivo.value, ahora=ahora
        )
        async with self._units() as u:
            await u.files.update(actualizado)
        return ExtractionOutcome(
            "unsupported", file=actualizado, reason=motivo
        )
