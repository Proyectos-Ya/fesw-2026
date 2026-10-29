from uuid import uuid4
import pytest

from app.domain.entities.question import Question
from app.domain.entities.supplier import Supplier


def test_question_entity_supports_tender_id_and_target_keyword() -> None:
    # Por defecto deben ser None
    q_default = Question(
        provider_id=uuid4(),
        question="¿Tiene grúa?",
        target_profile_field="maquinaria:grua",
    )
    assert q_default.tender_id is None
    assert q_default.target_keyword is None

    # Asignación explícita
    tender_id = uuid4()
    q_custom = Question(
        provider_id=uuid4(),
        tender_id=tender_id,
        target_keyword="maquinaria:grua",
        question="¿Tiene grúa?",
        target_profile_field="maquinaria:grua",
    )
    assert q_custom.tender_id == tender_id
    assert q_custom.target_keyword == "maquinaria:grua"


def test_supplier_entity_supports_negative_keywords() -> None:
    # Por defecto debe ser lista vacía
    s_default = Supplier(
        rut="76086428-5",
        legal_name="Empresa Test SpA",
    )
    assert s_default.negative_keywords == []

    # Permite guardar objetos con keyword y discarded_at
    item = {
        "keyword": "maquinaria:grua",
        "discarded_at": "2026-10-20T00:00:00Z",
    }
    s_custom = Supplier(
        rut="76086428-5",
        legal_name="Empresa Test SpA",
        negative_keywords=[item],
    )
    assert s_custom.negative_keywords == [item]
