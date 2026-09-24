from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from pydantic import ValidationError

from app.application.repositories.calendar_repository import (
    ICalendarEventLinkRepository,
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
    TenderMilestonesResult,
    changed,
    describe,
    get_tender,
    mercado_publico_milestones,
    merge_milestones,
    synced_providers_by_milestone,
)
from app.domain.entities.tender import Tender
from app.domain.entities.tender_chat import TenderChatDocument
from app.domain.entities.tender_milestone import (
    MilestoneKind,
    MilestoneSource,
    TenderMilestone,
)
from app.domain.errors.milestone_errors import InvalidMilestoneDate
from app.domain.services.milestone_date_normalizer import normalize_milestone_date
from app.shared.datetime_utils import CHILE_TZ, utc_now_naive


class ExtractTenderMilestonesUseCase:
    """Extrae con IA los hitos de las bases que el usuario subió (criterios 1 y 5)."""

    def __init__(
        self,
        tenders: ITenderRepository,
        milestones: ITenderMilestoneRepository,
        event_links: ICalendarEventLinkRepository,
        chat: ITenderChatRepository,
        ai: IMilestoneExtractionAIService,
        now: Callable[[], datetime] = utc_now_naive,
    ):
        self.tenders = tenders
        self.milestones = milestones
        self.event_links = event_links
        self.chat = chat
        self.ai = ai
        self.now = now

    async def execute(self, user_id: UUID, tender_id: UUID) -> TenderMilestonesResult:
        ahora = self.now()
        tender = await get_tender(self.tenders, tender_id)
        existentes = await self.milestones.list_for_tender(user_id, tender_id)

        # Los oficiales se guardan antes de llamar a la IA: si la IA falla, al
        # menos quedan publicación y cierre.
        oficiales = merge_milestones(existentes, mercado_publico_milestones(tender, user_id), ahora)
        await self.milestones.save_many(changed(existentes, oficiales))

        documentos = await self._documentos(user_id, tender_id)
        extraidos: list[ExtractedMilestone] = []
        if documentos:
            contextos = [contexto for _, contexto in documentos]
            extraidos = await self.ai.extract(contextos, _contexto(tender))

        candidatos, descartados = _a_hitos(extraidos, [d for d, _ in documentos], user_id, tender_id)
        de_ia = [m for m in existentes if m.source is MilestoneSource.IA_DOCUMENTO]
        nuevos = merge_milestones(de_ia, candidatos, ahora)
        await self.milestones.save_many(changed(de_ia, nuevos))
        await self._borrar_obsoletos(user_id, de_ia, nuevos)

        return await describe(
            await self.milestones.list_for_tender(user_id, tender_id),
            self.event_links,
            ahora,
            documents_count=len(documentos),
            discarded_count=descartados,
        )

    async def _documentos(
        self, user_id: UUID, tender_id: UUID
    ) -> list[tuple[TenderChatDocument, DocumentContextDTO]]:
        resultado = []
        for documento in await self.chat.get_documents_by_chat(user_id=user_id, tender_id=tender_id):
            contenido = await self.chat.get_document_bytes(documento.id, user_id)
            if not contenido:
                continue
            resultado.append(
                (
                    documento,
                    DocumentContextDTO(
                        document_name=documento.file_name,
                        file_type=documento.file_type,
                        file_bytes=contenido,
                    ),
                )
            )
        return resultado

    async def _borrar_obsoletos(
        self, user_id: UUID, previos: list[TenderMilestone], vigentes: list[TenderMilestone]
    ) -> None:
        """Quita los hitos de IA que ya no aparecen, salvo los que tienen un evento externo."""
        ids_vigentes = {m.id for m in vigentes}
        obsoletos = [m.id for m in previos if m.id not in ids_vigentes]
        if not obsoletos:
            return
        sincronizados = await synced_providers_by_milestone(self.event_links, obsoletos)
        await self.milestones.delete_many(user_id, [i for i in obsoletos if i not in sincronizados])


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
    documentos: list[TenderChatDocument],
    user_id: UUID,
    tender_id: UUID,
) -> tuple[list[TenderMilestone], int]:
    documento_por_nombre = {d.file_name: d.id for d in documentos}
    hitos: list[TenderMilestone] = []
    descartados = 0
    for extraido in extraidos:
        try:
            fecha = normalize_milestone_date(extraido.fecha, extraido.hora)
        except InvalidMilestoneDate:
            descartados += 1
            continue
        try:
            tipo = MilestoneKind(extraido.kind)
        except ValueError:
            tipo = MilestoneKind.OTRO
        try:
            hito = TenderMilestone(
                user_id=user_id,
                tender_id=tender_id,
                kind=tipo,
                title=extraido.title,
                description=extraido.description,
                source=MilestoneSource.IA_DOCUMENTO,
                source_document_id=documento_por_nombre.get(extraido.documento or ""),
                source_excerpt=extraido.texto_original,
                due_at=fecha.due_at,
                has_time=fecha.has_time,
            )
        except ValidationError:
            descartados += 1
            continue
        hitos.append(hito)
    return hitos, descartados
