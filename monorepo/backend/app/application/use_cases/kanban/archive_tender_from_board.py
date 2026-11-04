"""Archivado manual de una tarjeta del tablero Kanban (HdU 10 CA4 + HU-18).

Soft-delete: la tarjeta deja de aparecer en el tablero activo y pasa al
historial del workspace, de donde se puede restaurar mientras la razón sea
`manual`.
"""

from uuid import UUID

from app.application.repositories.kanban_event_repository import (
    IKanbanEventRepository,
)
from app.application.repositories.kanban_repository import IKanbanCardRepository
from app.application.use_cases.kanban.record_kanban_event import (
    RecordKanbanEventUseCase,
)
from app.domain.entities.kanban import ARCHIVE_REASON_MANUAL, KanbanCard
from app.domain.errors.kanban_errors import KanbanCardNotFound
from app.shared.datetime_utils import utc_now_naive


class ArchiveTenderFromBoardUseCase:
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
        card_id: UUID,
        tender_title: str | None = None,
    ) -> KanbanCard:
        card = await self.card_repo.get_by_id(card_id, supplier_id)
        # KanbanCardNotFound tiene (user_id, tender_id); acá no conocemos el
        # tender si la tarjeta no existe, pero el 404 solo necesita el mensaje
        # así que reusamos el error con el supplier_id como placeholder (los
        # metadatos no se exponen).
        if card is None:
            raise KanbanCardNotFound(supplier_id, card_id)
        # Si ya está archivada, es idempotente: devolvemos la misma.
        if card.archived_at is not None:
            return card
        card.archived_at = utc_now_naive()
        card.archived_reason = ARCHIVE_REASON_MANUAL
        card.updated_at = utc_now_naive()
        updated = await self.card_repo.update(card)
        if self.event_repo is not None:
            await RecordKanbanEventUseCase(self.event_repo).execute(
                supplier_id=supplier_id,
                user_id=user_id,
                event_type="card_archived",
                entity_type="card",
                entity_id=updated.id,
                tender_id=updated.tender_id,
                tender_title=tender_title,
                details={"reason": ARCHIVE_REASON_MANUAL},
            )
        return updated
