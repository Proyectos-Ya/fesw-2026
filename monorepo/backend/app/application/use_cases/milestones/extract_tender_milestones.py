from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from pydantic import ValidationError

from app.application.repositories.calendar_repository import (
    ICalendarEventLinkRepository,
)
from app.application.repositories.milestone_document_repository import (
    IMilestoneDocumentRepository,
)
from app.application.repositories.tender_chat_repository import ITenderChatRepository
from app.application.repositories.tender_milestone_repository import (
    ITenderMilestoneRepository,
)
from app.application.repositories.tender_repository import ITenderRepository
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
    remove_orphan_ai_milestones,
    save_official_milestones,
)
from app.domain.entities.tender import Tender
from app.domain.entities.tender_chat import TenderChatDocument
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


class ExtractTenderMilestonesUseCase:
    """Extrae con IA los hitos de las bases que el usuario subió (criterios 1 y 5).

    Cada documento se lee **una sola vez** y por separado. Volver a enviar las
    mismas bases daba títulos o fechas algo distintos, y la tabla terminaba con
    hitos duplicados o perdidos; un documento que falla tampoco arrastra a los
    demás. Para volver a leer una base, el usuario la borra y la sube de nuevo.
    """

    def __init__(
        self,
        tenders: ITenderRepository,
        milestones: ITenderMilestoneRepository,
        event_links: ICalendarEventLinkRepository,
        chat: ITenderChatRepository,
        ai: IMilestoneExtractionAIService,
        processed: IMilestoneDocumentRepository,
        now: Callable[[], datetime] = utc_now_naive,
    ):
        self.tenders = tenders
        self.milestones = milestones
        self.event_links = event_links
        self.chat = chat
        self.ai = ai
        self.processed = processed
        self.now = now

    async def execute(self, user_id: UUID, tender_id: UUID) -> TenderMilestonesResult:
        ahora = self.now()
        tender = await get_tender(self.tenders, tender_id)

        # Los oficiales se guardan antes de llamar a la IA: si la IA falla, al
        # menos quedan publicación y cierre.
        await save_official_milestones(self.milestones, self.event_links, tender, user_id, ahora)

        documentos = await self.chat.get_documents_by_chat(user_id=user_id, tender_id=tender_id)
        await remove_orphan_ai_milestones(
            self.milestones, self.event_links, user_id, tender_id, {d.id for d in documentos}
        )
        procesados = await self.processed.list_processed(user_id, tender_id)
        pendientes = [d for d in documentos if d.id not in procesados]

        leidos = perdidos = fallidos = descartados = 0
        for documento in pendientes:
            contenido = await self.chat.get_document_bytes(documento.id, user_id)
            if not contenido:
                # El disco del contenedor se borra en cada despliegue: el
                # registro sigue, el archivo no. Se avisa en vez de omitirlo.
                perdidos += 1
                continue
            try:
                extraidos = await self.ai.extract(
                    [
                        DocumentContextDTO(
                            document_name=documento.file_name,
                            file_type=documento.file_type,
                            file_bytes=contenido,
                        )
                    ],
                    _contexto(tender),
                )
            except MilestoneExtractionUnavailable:
                fallidos += 1
                continue
            encontrados, omitidos = await self._guardar(documento, extraidos, user_id, tender_id, ahora)
            descartados += omitidos
            await self.processed.mark_processed(user_id, tender_id, documento.id, encontrados, ahora)
            leidos += 1

        if fallidos and not leidos:
            # Nada se pudo leer: que la ficha lo muestre como falla y no como
            # "la IA no encontró plazos".
            raise MilestoneExtractionUnavailable()

        return await describe(
            await self.milestones.list_for_tender(user_id, tender_id),
            self.event_links,
            ahora,
            documents_count=len(documentos),
            discarded_count=descartados,
            unavailable_documents_count=perdidos,
            pending_documents_count=perdidos + fallidos,
            failed_documents_count=fallidos,
        )

    async def _guardar(
        self,
        documento: TenderChatDocument,
        extraidos: list[ExtractedMilestone],
        user_id: UUID,
        tender_id: UUID,
        ahora: datetime,
    ) -> tuple[int, int]:
        """Guarda los hitos de un documento; devuelve (guardados, descartados)."""
        candidatos, descartados = _a_hitos(extraidos, documento, user_id, tender_id)
        # Solo contra los hitos de este documento: los de otras bases y los
        # oficiales no se tocan.
        previos = [
            m
            for m in await self.milestones.list_for_tender(user_id, tender_id)
            if m.source is MilestoneSource.IA_DOCUMENTO and m.source_document_id == documento.id
        ]
        fusion = merge_ai_milestones(previos, candidatos, ahora)
        cambios = changed(previos, fusion)
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
    documento: TenderChatDocument,
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
                source_document_id=documento.id,
                source_excerpt=extraido.texto_original,
                due_at=fecha.due_at,
                has_time=fecha.has_time,
            )
        except ValidationError:
            descartados += 1
            continue
        hitos.append(hito)
    return hitos, descartados
