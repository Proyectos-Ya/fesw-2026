"""Archivado manual de una tarjeta del tablero Kanban (HdU 10, CA4).

Soft-delete: la tarjeta deja de aparecer en el tablero activo y pasa al
historial del usuario, de donde se puede restaurar mientras la razón sea
`manual`.
"""

from uuid import UUID

from app.application.repositories.kanban_repository import IKanbanCardRepository
from app.domain.entities.kanban import ARCHIVE_REASON_MANUAL, KanbanCard
from app.domain.errors.kanban_errors import KanbanCardNotFound
from app.shared.datetime_utils import utc_now_naive


class ArchiveTenderFromBoardUseCase:
    def __init__(self, card_repo: IKanbanCardRepository):
        self.card_repo = card_repo

    async def execute(self, user_id: UUID, card_id: UUID) -> KanbanCard:
        card = await self.card_repo.get_by_id(card_id, user_id)
        # `KanbanCardNotFound` tiene `(user_id, tender_id)`; acá no conocemos
        # el tender si la tarjeta no existe, pero el 404 solo necesita el
        # mensaje, así que reusamos el error con un placeholder (los metadatos
        # no se exponen).
        if card is None:
            raise KanbanCardNotFound(user_id, card_id)
        # Si ya está archivada, es idempotente: devolvemos la misma.
        if card.archived_at is not None:
            return card
        card.archived_at = utc_now_naive()
        card.archived_reason = ARCHIVE_REASON_MANUAL
        card.updated_at = utc_now_naive()
        return await self.card_repo.update(card)
