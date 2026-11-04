from uuid import UUID

from app.application.repositories.kanban_event_repository import (
    IKanbanEventRepository,
)
from app.application.repositories.kanban_repository import IKanbanCardRepository
from app.application.use_cases.kanban.record_kanban_event import (
    RecordKanbanEventUseCase,
)
from app.domain.errors.kanban_errors import KanbanCardNotFound


class RemoveTenderFromBoardUseCase:
    def __init__(
        self,
        card_repo: IKanbanCardRepository,
        event_repo: IKanbanEventRepository | None = None,
    ):
        self.card_repo = card_repo
        self.event_repo = event_repo

    async def execute(
        self,
        supplier_id: UUID,
        user_id: UUID,
        tender_id: UUID,
        tender_title: str | None = None,
    ) -> None:
        card = await self.card_repo.get(supplier_id, tender_id)
        if card is None:
            raise KanbanCardNotFound(supplier_id, tender_id)
        await self.card_repo.delete(supplier_id, tender_id)
        if self.event_repo is not None:
            await RecordKanbanEventUseCase(self.event_repo).execute(
                supplier_id=supplier_id,
                user_id=user_id,
                event_type="card_removed",
                entity_type="card",
                entity_id=card.id,
                tender_id=tender_id,
                tender_title=tender_title,
            )
