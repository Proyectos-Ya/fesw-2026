"""Auto-archivado por inactividad (HdU 10, CA4).

El scheduler diario llama a este caso de uso. Marca como `auto_3m` todas las
tarjetas activas cuyo `board_entered_at` sea anterior al corte configurado
(por defecto, 90 días). Las auto-archivadas quedan visibles en el historial
pero no se pueden restaurar: así se evita el "tablero infinito".
"""

from datetime import timedelta
from uuid import UUID

from app.application.repositories.kanban_repository import IKanbanCardRepository
from app.domain.entities.kanban import ARCHIVE_REASON_AUTO
from app.shared.datetime_utils import utc_now_naive

DEFAULT_AUTO_ARCHIVE_DAYS = 90


class AutoArchiveOldCardsUseCase:
    def __init__(
        self,
        card_repo: IKanbanCardRepository,
        age_days: int = DEFAULT_AUTO_ARCHIVE_DAYS,
    ):
        self.card_repo = card_repo
        self.age_days = age_days

    async def execute(self) -> list[UUID]:
        """Devuelve los IDs archivados en esta corrida (vacía si no hay nada)."""
        now = utc_now_naive()
        cutoff = now - timedelta(days=self.age_days)
        candidates = await self.card_repo.list_candidates_for_auto_archive(cutoff)
        archived_ids: list[UUID] = []
        for card in candidates:
            card.archived_at = now
            card.archived_reason = ARCHIVE_REASON_AUTO
            card.updated_at = now
            await self.card_repo.update(card)
            archived_ids.append(card.id)
        return archived_ids
