"""Tests TDD para el caso de uso `ReorderKanbanColumnsUseCase`.

Valida el reordenamiento de columnas del tablero Kanban en bloque:
- happy path: la lista nueva de posiciones se persiste correctamente.
- lista incompleta: faltan columnas del usuario.
- columna ajena: una id de la lista no pertenece al usuario.
- duplicados: la lista repite una id.
"""

from uuid import UUID, uuid4

import pytest

from app.application.repositories.kanban_repository import IKanbanColumnRepository
from app.application.use_cases.kanban.reorder_kanban_columns import (
    ReorderKanbanColumnsUseCase,
)
from app.domain.entities.kanban import KanbanColumn
from app.domain.errors.kanban_errors import KanbanColumnNotFound


class InMemoryKanbanColumnRepository(IKanbanColumnRepository):
    def __init__(self) -> None:
        self.columns: list[KanbanColumn] = []
        self.reorder_calls: list[tuple[UUID, list[UUID]]] = []

    async def get_by_user_id(self, user_id: UUID) -> list[KanbanColumn]:
        return [c for c in self.columns if c.user_id == user_id]

    async def get(self, column_id: UUID, user_id: UUID) -> KanbanColumn | None:
        return next(
            (c for c in self.columns if c.id == column_id and c.user_id == user_id),
            None,
        )

    async def create(self, column: KanbanColumn) -> KanbanColumn:
        self.columns.append(column)
        return column

    async def update(self, column: KanbanColumn) -> KanbanColumn:
        for i, c in enumerate(self.columns):
            if c.id == column.id:
                self.columns[i] = column
                return column
        raise KanbanColumnNotFound(column.id)

    async def delete(self, column_id: UUID, user_id: UUID) -> bool:
        before = len(self.columns)
        self.columns = [
            c for c in self.columns
            if not (c.id == column_id and c.user_id == user_id)
        ]
        return len(self.columns) < before

    async def count_cards(self, column_id: UUID) -> int:
        return 0

    async def reorder(
        self, user_id: UUID, ordered_ids: list[UUID]
    ) -> list[KanbanColumn]:
        self.reorder_calls.append((user_id, ordered_ids))
        for idx, col_id in enumerate(ordered_ids):
            for i, c in enumerate(self.columns):
                if c.id == col_id and c.user_id == user_id:
                    self.columns[i] = c.model_copy(update={"position": idx})
        return [
            c for c in self.columns if c.user_id == user_id
        ]


def _seed(repo: InMemoryKanbanColumnRepository, user_id: UUID, n: int) -> list[UUID]:
    ids: list[UUID] = []
    for i in range(n):
        col = KanbanColumn(user_id=user_id, name=f"Col {i}", position=i)
        repo.columns.append(col)
        ids.append(col.id)
    return ids


@pytest.mark.asyncio
async def test_reorder_happy_path_persists_new_positions() -> None:
    repo = InMemoryKanbanColumnRepository()
    user_id = uuid4()
    ids = _seed(repo, user_id, 4)
    new_order = [ids[2], ids[0], ids[3], ids[1]]

    use_case = ReorderKanbanColumnsUseCase(column_repo=repo)
    result = await use_case.execute(user_id=user_id, column_ids=new_order)

    assert repo.reorder_calls == [(user_id, new_order)]
    sorted_result = sorted(result, key=lambda c: c.position)
    assert [c.id for c in sorted_result] == new_order
    assert [c.position for c in sorted_result] == [0, 1, 2, 3]


@pytest.mark.asyncio
async def test_reorder_rejects_incomplete_list() -> None:
    repo = InMemoryKanbanColumnRepository()
    user_id = uuid4()
    ids = _seed(repo, user_id, 3)

    use_case = ReorderKanbanColumnsUseCase(column_repo=repo)
    with pytest.raises(ValueError, match="incompleta|falt"):
        await use_case.execute(user_id=user_id, column_ids=[ids[0], ids[1]])
    assert repo.reorder_calls == []


@pytest.mark.asyncio
async def test_reorder_rejects_column_from_other_user() -> None:
    repo = InMemoryKanbanColumnRepository()
    user_id = uuid4()
    other_id = uuid4()
    ids = _seed(repo, user_id, 2)
    # columna de otro usuario, mismo tamaño total
    foreign = KanbanColumn(user_id=other_id, name="Ajena", position=0)
    repo.columns.append(foreign)

    use_case = ReorderKanbanColumnsUseCase(column_repo=repo)
    with pytest.raises(KanbanColumnNotFound):
        await use_case.execute(
            user_id=user_id, column_ids=[ids[0], ids[1], foreign.id]
        )
    assert repo.reorder_calls == []


@pytest.mark.asyncio
async def test_reorder_rejects_duplicates() -> None:
    repo = InMemoryKanbanColumnRepository()
    user_id = uuid4()
    ids = _seed(repo, user_id, 3)

    use_case = ReorderKanbanColumnsUseCase(column_repo=repo)
    with pytest.raises(ValueError, match="duplicad|repit"):
        await use_case.execute(
            user_id=user_id, column_ids=[ids[0], ids[1], ids[1]]
        )
    assert repo.reorder_calls == []
