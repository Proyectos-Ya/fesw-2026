"""Pruebas unitarias de la entidad KanbanEvent (HU-18).

Cada mutación del tablero de un workspace deja un `KanbanEvent` en la tabla
`kanban_event`. La entidad modela el aviso individual; la escritura
sincrónica (dentro del mismo commit de transacción que la operación) es
responsabilidad del use case `record_kanban_event`.
"""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.entities.kanban_event import KanbanEvent


def test_requiere_supplier_id_user_id_y_event_type() -> None:
    with pytest.raises(ValidationError):
        KanbanEvent(user_id=uuid4(), event_type="card_added")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        KanbanEvent(supplier_id=uuid4(), event_type="card_added")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        KanbanEvent(supplier_id=uuid4(), user_id=uuid4())  # type: ignore[call-arg]


def test_defaults_dejan_details_vacio_y_opcionales_en_none() -> None:
    evento = KanbanEvent(
        supplier_id=uuid4(),
        user_id=uuid4(),
        event_type="column_created",
    )

    assert evento.details == {}
    assert evento.entity_type is None
    assert evento.entity_id is None
    assert evento.tender_id is None
    assert evento.tender_title is None
    assert evento.created_at is not None


def test_rechaza_event_type_desconocido() -> None:
    with pytest.raises(ValidationError):
        KanbanEvent(
            supplier_id=uuid4(),
            user_id=uuid4(),
            event_type="xyz",  # type: ignore[arg-type]
        )


def test_rechaza_entity_type_desconocido() -> None:
    with pytest.raises(ValidationError):
        KanbanEvent(
            supplier_id=uuid4(),
            user_id=uuid4(),
            event_type="card_added",
            entity_type="widget",  # type: ignore[arg-type]
        )


def test_acepta_evento_card_moved_con_details() -> None:
    tender_id = uuid4()
    evento = KanbanEvent(
        supplier_id=uuid4(),
        user_id=uuid4(),
        event_type="card_moved",
        entity_type="card",
        entity_id=uuid4(),
        tender_id=tender_id,
        tender_title="Suministro de materiales",
        details={"from_column": "Por revisar", "to_column": "Postulando"},
    )

    assert evento.event_type == "card_moved"
    assert evento.tender_id == tender_id
    assert evento.details["to_column"] == "Postulando"
