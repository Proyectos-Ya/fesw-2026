"""Pruebas unitarias de SavedTender (HU-18).

La licitación guardada pasa de ser personal (`user_id`) a ser del workspace
(`supplier_id`): todos los miembros del espacio comparten la misma lista y
guardarla es idempotente a nivel de workspace. `user_id` se mantiene como
auditoría ("quién la guardó primero").
"""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.entities.saved_tender import SavedTender


def test_requiere_supplier_id() -> None:
    with pytest.raises(ValidationError):
        SavedTender(user_id=uuid4(), tender_id=uuid4())  # type: ignore[call-arg]


def test_construye_con_los_cuatro_identificadores() -> None:
    supplier_id = uuid4()
    user_id = uuid4()
    tender_id = uuid4()

    guardada = SavedTender(
        supplier_id=supplier_id, user_id=user_id, tender_id=tender_id
    )

    assert guardada.supplier_id == supplier_id
    assert guardada.user_id == user_id
    assert guardada.tender_id == tender_id
    assert guardada.saved_at is not None
