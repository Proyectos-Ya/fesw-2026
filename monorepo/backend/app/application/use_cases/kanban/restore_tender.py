"""Restauración de una tarjeta archivada manualmente (HdU 10 CA4 + HU-18).

Las auto-archivadas (`auto_3m`) no se restauran: la regla de negocio es que
el usuario puede recuperar lo que archivó a mano; lo que se archivó por
inactividad se queda en el historial.
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
from app.domain.errors.kanban_errors import ArchiveNotRestorable, KanbanCardNotFound
from app.shared.datetime_utils import utc_now_naive


class RestoreTenderUseCase:
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
        if card is None:
            raise KanbanCardNotFound(supplier_id, card_id)
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
        updated = await self.card_repo.update(card)
        if self.event_repo is not None:
            await RecordKanbanEventUseCase(self.event_repo).execute(
                supplier_id=supplier_id,
                user_id=user_id,
                event_type="card_restored",
                entity_type="card",
                entity_id=updated.id,
                tender_id=updated.tender_id,
                tender_title=tender_title,
            )
        return updated
