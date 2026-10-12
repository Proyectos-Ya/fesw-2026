"""Restauración de una tarjeta archivada manualmente (HdU 10, CA4).

Las auto-archivadas (`auto_3m`) no se restauran: la regla de negocio es que
el usuario puede recuperar lo que archivó a mano; lo que se archivó por
inactividad se queda en el historial.
"""

from uuid import UUID

from app.application.repositories.kanban_repository import IKanbanCardRepository
from app.domain.entities.kanban import ARCHIVE_REASON_MANUAL, KanbanCard
from app.domain.errors.kanban_errors import ArchiveNotRestorable, KanbanCardNotFound
from app.shared.datetime_utils import utc_now_naive


class RestoreTenderUseCase:
    def __init__(self, card_repo: IKanbanCardRepository):
        self.card_repo = card_repo

    async def execute(self, user_id: UUID, card_id: UUID) -> KanbanCard:
        card = await self.card_repo.get_by_id(card_id, user_id)
        if card is None:
            raise KanbanCardNotFound(user_id, card_id)
        if card.archived_at is None:
            # Ya está activa: idempotente.
            return card
        if card.archived_reason != ARCHIVE_REASON_MANUAL:
            raise ArchiveNotRestorable(card_id, card.archived_reason or "unknown")
        card.archived_at = None
        card.archived_reason = None
        # Reseteamos el reloj de 90 días: el usuario acaba de "re-ingresar"
        # la tarjeta al tablero.
        card.board_entered_at = utc_now_naive()
        card.updated_at = utc_now_naive()
        return await self.card_repo.update(card)
