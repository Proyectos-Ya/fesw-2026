"""Tests TDD para el atributo color de las columnas del tablero Kanban."""

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.application.repositories.kanban_repository import IKanbanColumnRepository
from app.application.schemas.kanban_schema import KanbanColumnCreate, KanbanColumnUpdate
from app.application.use_cases.kanban.create_kanban_column import CreateKanbanColumnUseCase
from app.application.use_cases.kanban.list_kanban_columns import ListKanbanColumnsUseCase
from app.application.use_cases.kanban.update_kanban_column import UpdateKanbanColumnUseCase
from app.domain.entities.kanban import DEFAULT_COLUMN_COLORS, DEFAULT_COLUMNS, KanbanColumn
from app.domain.errors.kanban_errors import KanbanColumnNotFound


class InMemoryKanbanColumnRepository(IKanbanColumnRepository):
    def __init__(self) -> None:
        self.columns: list[KanbanColumn] = []

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


# ---------------------------------------------------------------------------
# Validación de hex en los schemas
# ---------------------------------------------------------------------------


def test_valid_hex_passes_create_schema() -> None:
    for hex_val in ("#A99A7C", "#000000", "#ffffff", "#BF6E4A", "#AABBCC"):
        schema = KanbanColumnCreate(name="Col", color=hex_val)
        assert schema.color == hex_val


def test_invalid_hex_raises_in_create_schema() -> None:
    for bad in ("rojo", "#GGG", "#12345", "A99A7C", "#1234567", ""):
        with pytest.raises(ValidationError):
            KanbanColumnCreate(name="Col", color=bad)


def test_valid_hex_passes_update_schema() -> None:
    schema = KanbanColumnUpdate(color="#5C7A52")
    assert schema.color == "#5C7A52"


def test_invalid_hex_raises_in_update_schema() -> None:
    with pytest.raises(ValidationError):
        KanbanColumnUpdate(color="verde")


def test_none_color_is_allowed_in_create_and_update() -> None:
    assert KanbanColumnCreate(name="Col", color=None).color is None
    assert KanbanColumnUpdate(color=None).color is None


# ---------------------------------------------------------------------------
# CreateKanbanColumnUseCase — auto-asignación cíclica de color
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_new_column_auto_assigns_first_color_when_board_is_empty() -> None:
    repo = InMemoryKanbanColumnRepository()
    use_case = CreateKanbanColumnUseCase(column_repo=repo)
    user_id = uuid4()

    col = await use_case.execute(user_id=user_id, name="Primera", position=None, color=None)

    assert col.color == DEFAULT_COLUMN_COLORS[0]


@pytest.mark.asyncio
async def test_new_column_cycles_through_palette() -> None:
    repo = InMemoryKanbanColumnRepository()
    use_case = CreateKanbanColumnUseCase(column_repo=repo)
    user_id = uuid4()

    palette_len = len(DEFAULT_COLUMN_COLORS)
    for i in range(palette_len + 2):
        await use_case.execute(user_id=user_id, name=f"Col {i}", position=None, color=None)

    colors = [c.color for c in repo.columns]
    assert colors[4] == DEFAULT_COLUMN_COLORS[4]
    assert colors[palette_len] == DEFAULT_COLUMN_COLORS[0]
    assert colors[palette_len + 1] == DEFAULT_COLUMN_COLORS[1]


@pytest.mark.asyncio
async def test_explicit_color_overrides_auto_assignment() -> None:
    repo = InMemoryKanbanColumnRepository()
    use_case = CreateKanbanColumnUseCase(column_repo=repo)
    user_id = uuid4()

    col = await use_case.execute(user_id=user_id, name="Custom", position=None, color="#FF0000")

    assert col.color == "#FF0000"


# ---------------------------------------------------------------------------
# ListKanbanColumnsUseCase — columnas por defecto con colores emparejados
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_default_columns_get_paired_colors() -> None:
    repo = InMemoryKanbanColumnRepository()
    use_case = ListKanbanColumnsUseCase(column_repo=repo)
    user_id = uuid4()

    result = await use_case.execute(user_id=user_id)

    assert len(result) == len(DEFAULT_COLUMNS)
    for i, response in enumerate(result):
        assert response.color == DEFAULT_COLUMN_COLORS[i], (
            f"Columna '{DEFAULT_COLUMNS[i]}' debería tener color "
            f"{DEFAULT_COLUMN_COLORS[i]!r}, tiene {response.color!r}"
        )


@pytest.mark.asyncio
async def test_existing_columns_preserve_their_color() -> None:
    repo = InMemoryKanbanColumnRepository()
    user_id = uuid4()
    custom_color = "#123456"
    repo.columns.append(
        KanbanColumn(user_id=user_id, name="Mi columna", position=0, color=custom_color)
    )

    use_case = ListKanbanColumnsUseCase(column_repo=repo)
    result = await use_case.execute(user_id=user_id)

    assert result[0].color == custom_color


# ---------------------------------------------------------------------------
# UpdateKanbanColumnUseCase — actualizar color
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_column_changes_color() -> None:
    repo = InMemoryKanbanColumnRepository()
    user_id = uuid4()
    col = KanbanColumn(user_id=user_id, name="Col", position=0, color="#A99A7C")
    repo.columns.append(col)

    use_case = UpdateKanbanColumnUseCase(column_repo=repo)
    updated = await use_case.execute(
        column_id=col.id, user_id=user_id, name=None, position=None, color="#35645B"
    )

    assert updated.color == "#35645B"


@pytest.mark.asyncio
async def test_update_column_preserves_color_when_not_provided() -> None:
    repo = InMemoryKanbanColumnRepository()
    user_id = uuid4()
    original_color = "#BF6E4A"
    col = KanbanColumn(user_id=user_id, name="Col", position=0, color=original_color)
    repo.columns.append(col)

    use_case = UpdateKanbanColumnUseCase(column_repo=repo)
    updated = await use_case.execute(
        column_id=col.id, user_id=user_id, name="Nuevo nombre", position=None, color=None
    )

    assert updated.color == original_color
    assert updated.name == "Nuevo nombre"
