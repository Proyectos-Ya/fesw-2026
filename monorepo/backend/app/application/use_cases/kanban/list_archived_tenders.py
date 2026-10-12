"""Historial de tarjetas archivadas de un usuario (HdU 10, CA4)."""

from uuid import UUID

from app.application.repositories.kanban_repository import IKanbanCardRepository
from app.application.schemas.kanban_schema import KanbanArchiveResponse


class ListArchivedTendersUseCase:
    def __init__(self, card_repo: IKanbanCardRepository):
        self.card_repo = card_repo

    async def execute(self, user_id: UUID) -> list[KanbanArchiveResponse]:
        rows = await self.card_repo.list_archived_with_context(user_id)
        return [
            KanbanArchiveResponse(
                id=card.id,
                tender_id=card.tender_id,
                tender_title=tender_name,
                tender_external_id=tender_code,
                column_id=card.column_id,
                column_name=column_name,
                board_entered_at=card.board_entered_at,
                archived_at=card.archived_at,  # type: ignore[arg-type]
                archived_reason=card.archived_reason or "",
            )
            for (card, column_name, tender_code, tender_name) in rows
        ]
