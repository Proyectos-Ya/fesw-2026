from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from app.application.repositories.calendar_repository import (
    ICalendarEventLinkRepository,
)
from app.application.repositories.tender_chat_repository import ITenderChatRepository
from app.application.repositories.tender_milestone_repository import (
    ITenderMilestoneRepository,
)
from app.application.repositories.tender_repository import ITenderRepository
from app.application.use_cases.milestones.milestone_views import (
    TenderMilestonesResult,
    changed,
    describe,
    get_tender,
    mercado_publico_milestones,
    merge_milestones,
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
        now: Callable[[], datetime] = utc_now_naive,
    ):
        self.tenders = tenders
        self.milestones = milestones
        self.event_links = event_links
        self.chat = chat
        self.now = now

    async def execute(self, user_id: UUID, tender_id: UUID) -> TenderMilestonesResult:
        ahora = self.now()
        tender = await get_tender(self.tenders, tender_id)
        existentes = await self.milestones.list_for_tender(user_id, tender_id)

        oficiales = merge_milestones(existentes, mercado_publico_milestones(tender, user_id), ahora)
        pendientes = changed(existentes, oficiales)
        if pendientes:
            await self.milestones.save_many(pendientes)
            existentes = await self.milestones.list_for_tender(user_id, tender_id)

        documentos = await self.chat.get_documents_by_chat(user_id=user_id, tender_id=tender_id)
        return await describe(existentes, self.event_links, ahora, len(documentos))
