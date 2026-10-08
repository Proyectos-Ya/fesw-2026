"""Tests TDD para HdU 10 CA4: archivado, historial, restauración y auto-archivado."""

from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.application.repositories.kanban_repository import IKanbanCardRepository
from app.application.use_cases.kanban.archive_tender_from_board import (
    ArchiveTenderFromBoardUseCase,
)
from app.application.use_cases.kanban.auto_archive_old_cards import (
    AutoArchiveOldCardsUseCase,
)
from app.application.use_cases.kanban.list_archived_tenders import (
    ListArchivedTendersUseCase,
)
from app.application.use_cases.kanban.restore_tender import RestoreTenderUseCase
from app.domain.entities.kanban import (
    ARCHIVE_REASON_AUTO,
    ARCHIVE_REASON_MANUAL,
    KanbanCard,
)
from app.domain.errors.kanban_errors import ArchiveNotRestorable, KanbanCardNotFound


class InMemoryKanbanCardRepository(IKanbanCardRepository):
    """Fake en memoria para los tests de archivado (CA4)."""

    def __init__(self) -> None:
        self.cards: list[KanbanCard] = []
        # El historial enriquecido necesita saber de columnas y licitaciones:
        # como el fake no las tiene, devolvemos lo mínimo que piden los tests
        # (nombre de columna y datos de la licitación).
        self.column_names: dict[UUID, str] = {}
        self.tender_meta: dict[UUID, tuple[str, str]] = {}

    async def get_by_user_id(self, user_id: UUID) -> list[KanbanCard]:
        return [
            c for c in self.cards
            if c.user_id == user_id and c.archived_at is None
        ]

    async def get(self, user_id: UUID, tender_id: UUID) -> KanbanCard | None:
        return next(
            (
                c for c in self.cards
                if c.user_id == user_id
                and c.tender_id == tender_id
                and c.archived_at is None
            ),
            None,
        )

    async def get_by_id(self, card_id: UUID, user_id: UUID) -> KanbanCard | None:
        return next(
            (c for c in self.cards if c.id == card_id and c.user_id == user_id),
            None,
        )

    async def create(self, card: KanbanCard) -> KanbanCard:
        self.cards.append(card)
        return card

    async def update(self, card: KanbanCard) -> KanbanCard:
        for i, c in enumerate(self.cards):
            if c.id == card.id:
                self.cards[i] = card
                return card
        raise KanbanCardNotFound(card.user_id, card.tender_id)

    async def delete(self, user_id: UUID, tender_id: UUID) -> bool:
        before = len(self.cards)
        self.cards = [
            c for c in self.cards
            if not (
                c.user_id == user_id
                and c.tender_id == tender_id
                and c.archived_at is None
            )
        ]
        return len(self.cards) < before

    async def list_archived(self, user_id: UUID) -> list[KanbanCard]:
        archived = [
            c for c in self.cards
            if c.user_id == user_id and c.archived_at is not None
        ]
        return sorted(archived, key=lambda c: c.archived_at, reverse=True)  # type: ignore[arg-type,return-value]

    async def list_archived_with_context(
        self, user_id: UUID
    ) -> list[tuple[KanbanCard, str, str, str]]:
        archived = await self.list_archived(user_id)
        rows: list[tuple[KanbanCard, str, str, str]] = []
        for card in archived:
            column_name = self.column_names.get(card.column_id, "Columna")
            code, name = self.tender_meta.get(card.tender_id, ("CODE", "Nombre"))
            rows.append((card, column_name, code, name))
        return rows

    async def list_candidates_for_auto_archive(
        self, cutoff: datetime
    ) -> list[KanbanCard]:
        return [
            c for c in self.cards
            if c.archived_at is None and c.board_entered_at < cutoff
        ]


# ---------------------------------------------------------------------------
# ArchiveTenderFromBoardUseCase
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_archive_marks_card_with_manual_reason_and_timestamp() -> None:
    repo = InMemoryKanbanCardRepository()
    user_id = uuid4()
    card = KanbanCard(
        user_id=user_id, tender_id=uuid4(), column_id=uuid4(), position=0
    )
    repo.cards.append(card)

    use_case = ArchiveTenderFromBoardUseCase(card_repo=repo)
    archived = await use_case.execute(user_id=user_id, card_id=card.id)

    assert archived.archived_at is not None
    assert archived.archived_reason == ARCHIVE_REASON_MANUAL


@pytest.mark.asyncio
async def test_archive_removes_card_from_active_board() -> None:
    repo = InMemoryKanbanCardRepository()
    user_id = uuid4()
    card = KanbanCard(
        user_id=user_id, tender_id=uuid4(), column_id=uuid4(), position=0
    )
    repo.cards.append(card)

    use_case = ArchiveTenderFromBoardUseCase(card_repo=repo)
    await use_case.execute(user_id=user_id, card_id=card.id)

    active = await repo.get_by_user_id(user_id)
    assert active == []


@pytest.mark.asyncio
async def test_archive_unknown_card_raises_not_found() -> None:
    repo = InMemoryKanbanCardRepository()
    use_case = ArchiveTenderFromBoardUseCase(card_repo=repo)
    with pytest.raises(KanbanCardNotFound):
        await use_case.execute(user_id=uuid4(), card_id=uuid4())


@pytest.mark.asyncio
async def test_archive_is_idempotent_on_already_archived() -> None:
    repo = InMemoryKanbanCardRepository()
    user_id = uuid4()
    original_ts = datetime(2026, 1, 1, 12, 0, 0)
    card = KanbanCard(
        user_id=user_id,
        tender_id=uuid4(),
        column_id=uuid4(),
        position=0,
        archived_at=original_ts,
        archived_reason=ARCHIVE_REASON_MANUAL,
    )
    repo.cards.append(card)

    use_case = ArchiveTenderFromBoardUseCase(card_repo=repo)
    result = await use_case.execute(user_id=user_id, card_id=card.id)

    assert result.archived_at == original_ts


# ---------------------------------------------------------------------------
# RestoreTenderUseCase
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_restore_manual_archive_clears_timestamp_and_reason() -> None:
    repo = InMemoryKanbanCardRepository()
    user_id = uuid4()
    card = KanbanCard(
        user_id=user_id,
        tender_id=uuid4(),
        column_id=uuid4(),
        position=0,
        archived_at=datetime(2026, 1, 1),
        archived_reason=ARCHIVE_REASON_MANUAL,
    )
    repo.cards.append(card)

    use_case = RestoreTenderUseCase(card_repo=repo)
    restored = await use_case.execute(user_id=user_id, card_id=card.id)

    assert restored.archived_at is None
    assert restored.archived_reason is None


@pytest.mark.asyncio
async def test_restore_auto_archive_raises_not_restorable() -> None:
    repo = InMemoryKanbanCardRepository()
    user_id = uuid4()
    card = KanbanCard(
        user_id=user_id,
        tender_id=uuid4(),
        column_id=uuid4(),
        position=0,
        archived_at=datetime(2026, 1, 1),
        archived_reason=ARCHIVE_REASON_AUTO,
    )
    repo.cards.append(card)

    use_case = RestoreTenderUseCase(card_repo=repo)
    with pytest.raises(ArchiveNotRestorable):
        await use_case.execute(user_id=user_id, card_id=card.id)


@pytest.mark.asyncio
async def test_restore_unknown_card_raises_not_found() -> None:
    repo = InMemoryKanbanCardRepository()
    use_case = RestoreTenderUseCase(card_repo=repo)
    with pytest.raises(KanbanCardNotFound):
        await use_case.execute(user_id=uuid4(), card_id=uuid4())


# ---------------------------------------------------------------------------
# ListArchivedTendersUseCase
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_archived_returns_desc_by_archived_at() -> None:
    repo = InMemoryKanbanCardRepository()
    user_id = uuid4()
    column_id = uuid4()
    repo.column_names[column_id] = "En revisión"

    def make(archived_at: datetime, label: str) -> KanbanCard:
        tender_id = uuid4()
        repo.tender_meta[tender_id] = (f"T-{label}", f"Lic {label}")
        return KanbanCard(
            user_id=user_id,
            tender_id=tender_id,
            column_id=column_id,
            position=0,
            archived_at=archived_at,
            archived_reason=ARCHIVE_REASON_MANUAL,
        )

    older = make(datetime(2026, 1, 1), "vieja")
    newer = make(datetime(2026, 2, 1), "nueva")
    repo.cards.extend([older, newer])

    use_case = ListArchivedTendersUseCase(card_repo=repo)
    result = await use_case.execute(user_id=user_id)

    assert [r.archived_at for r in result] == [newer.archived_at, older.archived_at]
    assert result[0].column_name == "En revisión"
    assert result[0].tender_title == "Lic nueva"
    assert result[1].tender_title == "Lic vieja"


# ---------------------------------------------------------------------------
# AutoArchiveOldCardsUseCase
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scheduler_archives_only_cards_older_than_cutoff() -> None:
    repo = InMemoryKanbanCardRepository()
    user_id = uuid4()
    now = datetime.utcnow()

    old = KanbanCard(
        user_id=user_id,
        tender_id=uuid4(),
        column_id=uuid4(),
        position=0,
        board_entered_at=now - timedelta(days=100),
    )
    fresh = KanbanCard(
        user_id=user_id,
        tender_id=uuid4(),
        column_id=uuid4(),
        position=1,
        board_entered_at=now - timedelta(days=30),
    )
    repo.cards.extend([old, fresh])

    use_case = AutoArchiveOldCardsUseCase(card_repo=repo, age_days=90)
    archived_ids = await use_case.execute()

    assert archived_ids == [old.id]
    reloaded_old = await repo.get_by_id(old.id, user_id)
    reloaded_fresh = await repo.get_by_id(fresh.id, user_id)
    assert reloaded_old is not None and reloaded_old.archived_reason == ARCHIVE_REASON_AUTO
    assert reloaded_fresh is not None and reloaded_fresh.archived_at is None


@pytest.mark.asyncio
async def test_scheduler_ignores_already_archived_cards() -> None:
    repo = InMemoryKanbanCardRepository()
    user_id = uuid4()
    now = datetime.utcnow()
    card = KanbanCard(
        user_id=user_id,
        tender_id=uuid4(),
        column_id=uuid4(),
        position=0,
        board_entered_at=now - timedelta(days=200),
        archived_at=now - timedelta(days=5),
        archived_reason=ARCHIVE_REASON_MANUAL,
    )
    repo.cards.append(card)

    use_case = AutoArchiveOldCardsUseCase(card_repo=repo, age_days=90)
    archived_ids = await use_case.execute()

    assert archived_ids == []
    # Mantiene su razón manual, no la pisamos.
    reloaded = await repo.get_by_id(card.id, user_id)
    assert reloaded is not None and reloaded.archived_reason == ARCHIVE_REASON_MANUAL
