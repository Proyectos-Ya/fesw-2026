from collections.abc import Callable
from datetime import datetime
from uuid import UUID

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
from app.application.services.milestone_extraction_background import (
    IMilestoneExtractionBackground,
    MilestoneExtractionStatus,
)
from app.application.use_cases.milestones.milestone_views import (
    TenderMilestonesResult,
    describe,
    get_tender,
    remove_orphan_ai_milestones,
    save_official_milestones,
)
from app.shared.datetime_utils import utc_now_naive


class GetTenderMilestonesUseCase:
    """Hitos de la licitación para el usuario.

    Los de Mercado Público se guardan (o actualizan) al consultar: tienen que
    existir con id propio para poder elegirlos y sincronizarlos.
    """

    def __init__(
        self,
        tenders: ITenderRepository,
        milestones: ITenderMilestoneRepository,
        event_links: ICalendarEventLinkRepository,
        chat: ITenderChatRepository,
        processed: IMilestoneDocumentRepository,
        extraction: IMilestoneExtractionBackground | None = None,
        now: Callable[[], datetime] = utc_now_naive,
    ):
        self.tenders = tenders
        self.milestones = milestones
        self.event_links = event_links
        self.chat = chat
        self.processed = processed
        self.extraction = extraction
        self.now = now

    async def execute(self, user_id: UUID, tender_id: UUID) -> TenderMilestonesResult:
        ahora = self.now()
        tender = await get_tender(self.tenders, tender_id)
        await save_official_milestones(self.milestones, self.event_links, tender, user_id, ahora)

        documentos = await self.chat.get_documents_by_chat(user_id=user_id, tender_id=tender_id)
        # Al borrar una base en el asistente, sus hitos se van en la próxima consulta.
        await remove_orphan_ai_milestones(
            self.milestones, self.event_links, user_id, tender_id, {d.id for d in documentos}
        )
        procesados = await self.processed.list_processed(user_id, tender_id)
        estado = (
            self.extraction.status(user_id, tender_id)
            if self.extraction is not None
            else MilestoneExtractionStatus.IDLE
        )
        return await describe(
            await self.milestones.list_for_tender(user_id, tender_id),
            self.event_links,
            ahora,
            len(documentos),
            extraction_status=estado,
            pending_documents_count=sum(1 for d in documentos if d.id not in procesados),
        )
