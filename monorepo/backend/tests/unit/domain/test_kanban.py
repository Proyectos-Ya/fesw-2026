"""Pruebas unitarias de las entidades KanbanColumn y KanbanCard.

HU-18: el tablero pertenece al workspace (`supplier_id`), no al usuario.
`user_id` se mantiene como autoría ("quién lo creó / agregó"), no propiedad.
"""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.entities.kanban import KanbanCard, KanbanColumn


class TestKanbanColumn:
    def test_requiere_supplier_id(self) -> None:
        with pytest.raises(ValidationError):
            KanbanColumn(user_id=uuid4(), name="Por revisar", position=0)  # type: ignore[call-arg]

    def test_expone_supplier_id_como_atributo(self) -> None:
        supplier_id = uuid4()
        columna = KanbanColumn(
            supplier_id=supplier_id,
            user_id=uuid4(),
            name="Por revisar",
            position=0,
        )

        assert columna.supplier_id == supplier_id

    def test_mantiene_user_id_como_autoria(self) -> None:
        # user_id sigue existiendo como autoría: supplier_id = propiedad,
        # user_id = quién la creó.
        user_id = uuid4()
        columna = KanbanColumn(
            supplier_id=uuid4(),
            user_id=user_id,
            name="En revisión",
            position=1,
        )

        assert columna.user_id == user_id


class TestKanbanCard:
    def test_requiere_supplier_id(self) -> None:
        with pytest.raises(ValidationError):
            KanbanCard(  # type: ignore[call-arg]
                user_id=uuid4(),
                tender_id=uuid4(),
                column_id=uuid4(),
                position=0,
            )

    def test_expone_supplier_id_como_atributo(self) -> None:
        supplier_id = uuid4()
        tarjeta = KanbanCard(
            supplier_id=supplier_id,
            user_id=uuid4(),
            tender_id=uuid4(),
            column_id=uuid4(),
            position=0,
        )

        assert tarjeta.supplier_id == supplier_id
