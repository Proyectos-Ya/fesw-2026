import logging
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from pydantic import ValidationError

from app.application.repositories.attachment_file_repository import (
    IAttachmentFileRepository,
)
from app.application.repositories.calendar_repository import (
    ICalendarEventLinkRepository,
)
from app.application.repositories.milestone_attachment_repository import (
    IMilestoneAttachmentRepository,
)
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.tender_attachment_repository import (
    ITenderAttachmentRepository,
)
from app.application.repositories.tender_milestone_repository import (
    ITenderMilestoneRepository,
)
from app.application.repositories.tender_repository import ITenderRepository
from app.application.services.anexos_visibles import AnexoVisible, anexos_visibles
from app.application.services.attachment_storage import IAttachmentStorage
from app.application.services.milestone_extraction_ai_service import (
    ExtractedMilestone,
    IMilestoneExtractionAIService,
)
from app.application.services.tender_assistant_ai_service import DocumentContextDTO
from app.application.use_cases.milestones.milestone_views import (
    OFFICIAL_KINDS,
    TenderMilestonesResult,
    changed,
    describe,
    get_tender,
    merge_ai_milestones,
    remove_orphan_file_milestones,
    save_official_milestones,
)
from app.application.use_cases.supplier.resolver_empresa import resolver_empresa
from app.domain.entities.tender import Tender
from app.domain.entities.tender_milestone import (
    MilestoneKind,
    MilestoneSource,
    TenderMilestone,
)
from app.domain.errors.milestone_errors import (
    InvalidMilestoneDate,
    MilestoneExtractionUnavailable,
)
from app.domain.services.milestone_date_normalizer import normalize_milestone_date
from app.shared.datetime_utils import CHILE_TZ, utc_now_naive

logger = logging.getLogger(__name__)


async def empresa_del_usuario(
    suppliers: ISupplierRepository, user_id: UUID, workspace_id: UUID | None
) -> UUID | None:
    """La empresa activa si viene; si no, la propia del usuario (`resolver_empresa`)."""
    if workspace_id is not None:
        return workspace_id
    empresa = await resolver_empresa(suppliers, user_id, None)
    return empresa.id if empresa is not None else None


class ExtractTenderMilestonesUseCase:
    """Extrae con IA los hitos de los anexos que ve la empresa (criterios 1 y 5, plan 233).

    Cada anexo se lee **una sola vez** por usuario y por separado. Volver a
    enviar las mismas bases daba títulos o fechas algo distintos, y la tabla
    terminaba con hitos duplicados o perdidos; un anexo que falla tampoco
    arrastra a los demás. Los hitos que salieron antes de los documentos del chat
    se conservan.
    """

    def __init__(
        self,
        tenders: ITenderRepository,
        milestones: ITenderMilestoneRepository,
        event_links: ICalendarEventLinkRepository,
        files: IAttachmentFileRepository,
        attachments: ITenderAttachmentRepository,
        storage: IAttachmentStorage | None,
        ai: IMilestoneExtractionAIService,
        processed: IMilestoneAttachmentRepository,
        suppliers: ISupplierRepository,
        now: Callable[[], datetime] = utc_now_naive,
    ):
        self.tenders = tenders
        self.milestones = milestones
        self.event_links = event_links
        self.files = files
        self.attachments = attachments
        self.storage = storage
        self.ai = ai
        self.processed = processed
        self.suppliers = suppliers
        self.now = now

    async def execute(
        self, user_id: UUID, tender_id: UUID, workspace_id: UUID | None = None
    ) -> TenderMilestonesResult:
        ahora = self.now()
        tender = await get_tender(self.tenders, tender_id)

        # Los oficiales se guardan antes de llamar a la IA: si la IA falla, al
        # menos quedan publicación y cierre.
        await save_official_milestones(self.milestones, self.event_links, tender, user_id, ahora)

        empresa = await empresa_del_usuario(self.suppliers, user_id, workspace_id)
        anexos = await anexos_visibles(
            self.files, self.attachments, tender_id=tender_id, workspace_id=empresa
        )
        await remove_orphan_file_milestones(
            self.milestones, self.event_links, user_id, tender_id, {a.archivo.id for a in anexos}
        )
        procesados = await self.processed.list_processed(user_id, tender_id)
        pendientes = [a for a in anexos if a.archivo.id not in procesados]

        leidos = perdidos = fallidos = descartados = 0
        for anexo in pendientes:
            if not anexo.legible:
                # La IA no sabe leerlo: se marca para que no quede pendiente para siempre.
                await self.processed.mark_processed(user_id, tender_id, anexo.archivo.id, 0, ahora)
                continue
            contenido = await self._contenido(anexo)
            if not contenido:
                # El registro existe pero el objeto no: se avisa en vez de omitirlo.
                perdidos += 1
                continue
            try:
                extraidos = await self.ai.extract(
                    [
                        DocumentContextDTO(
                            document_name=anexo.nombre,
                            file_type=anexo.tipo,
                            file_bytes=contenido,
                        )
                    ],
                    _contexto(tender),
                )
            except MilestoneExtractionUnavailable:
                fallidos += 1
                continue
            encontrados, omitidos = await self._guardar(anexo, extraidos, user_id, tender_id, ahora)
            descartados += omitidos
            await self.processed.mark_processed(
                user_id, tender_id, anexo.archivo.id, encontrados, ahora
            )
            leidos += 1

        if fallidos and not leidos:
            # Nada se pudo leer: que la ficha lo muestre como falla y no como
            # "la IA no encontró plazos".
            raise MilestoneExtractionUnavailable()

        return await describe(
            await self.milestones.list_for_tender(user_id, tender_id),
            self.event_links,
            ahora,
            documents_count=len(anexos),
            discarded_count=descartados,
            unavailable_documents_count=perdidos,
            pending_documents_count=perdidos + fallidos,
            failed_documents_count=fallidos,
        )

    async def _contenido(self, anexo: AnexoVisible) -> bytes | None:
        if self.storage is None:
            return None
        try:
            return await self.storage.get_bytes(anexo.archivo.storage_key)
        except Exception:
            logger.warning(
                "No se pudo leer el anexo %s para extraer hitos.", anexo.archivo.id, exc_info=True
            )
            return None

    async def _guardar(
        self,
        anexo: AnexoVisible,
        extraidos: list[ExtractedMilestone],
        user_id: UUID,
        tender_id: UUID,
        ahora: datetime,
    ) -> tuple[int, int]:
        """Guarda los hitos de un anexo; devuelve (guardados, descartados).

        Se compara con todos los hitos de IA del usuario en la licitación: si ya
        hay uno equivalente de otra fuente (otro anexo o el chat), se conserva tal
        cual, con su recordatorio y su evento de calendario. Los oficiales no se
        tocan.
        """
        candidatos, descartados = _a_hitos(extraidos, anexo.archivo.id, user_id, tender_id)
        de_ia = [
            m
            for m in await self.milestones.list_for_tender(user_id, tender_id)
            if m.source is MilestoneSource.IA_DOCUMENTO
        ]
        fusion = merge_ai_milestones(de_ia, candidatos, ahora)
        de_otra_fuente = {m.id for m in de_ia if m.source_file_id != anexo.archivo.id}
        propios = [m for m in fusion if m.id not in de_otra_fuente]
        cambios = changed([m for m in de_ia if m.id not in de_otra_fuente], propios)
        if cambios:
            await self.milestones.save_many(cambios)
        return len(fusion), descartados


def _contexto(tender: Tender) -> str:
    def local(fecha: datetime) -> str:
        return fecha.replace(tzinfo=UTC).astimezone(CHILE_TZ).strftime("%Y-%m-%d %H:%M")

    return (
        f"Licitación {tender.code}: {tender.name}.\n"
        f"Publicación: {local(tender.published_at)} (hora de Chile).\n"
        f"Cierre de recepción de ofertas: {local(tender.closing_at)} (hora de Chile).\n"
        "Usa estas fechas como referencia para resolver fechas relativas o sin mes ni año."
    )


def _a_hitos(
    extraidos: list[ExtractedMilestone],
    archivo_id: UUID,
    user_id: UUID,
    tender_id: UUID,
) -> tuple[list[TenderMilestone], int]:
    hitos: list[TenderMilestone] = []
    descartados = 0
    for extraido in extraidos:
        try:
            tipo = MilestoneKind(extraido.kind)
        except ValueError:
            tipo = MilestoneKind.OTRO
        if tipo in OFFICIAL_KINDS:
            # Publicación y cierre vienen de Mercado Público y se actualizan solos.
            continue
        try:
            fecha = normalize_milestone_date(extraido.fecha, extraido.hora)
        except InvalidMilestoneDate:
            descartados += 1
            continue
        try:
            hito = TenderMilestone(
                user_id=user_id,
                tender_id=tender_id,
                kind=tipo,
                title=extraido.title,
                description=extraido.description,
                source=MilestoneSource.IA_DOCUMENTO,
                source_file_id=archivo_id,
                source_excerpt=extraido.texto_original,
                due_at=fecha.due_at,
                has_time=fecha.has_time,
            )
        except ValidationError:
            descartados += 1
            continue
        hitos.append(hito)
    return hitos, descartados
