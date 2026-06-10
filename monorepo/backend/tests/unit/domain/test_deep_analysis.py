import pytest
from uuid import uuid4
from pydantic import ValidationError
from datetime import datetime, timezone

from app.domain.entities.deep_analysis import DeepAnalysis


def test_create_valid_deep_analysis():
    tender_id = uuid4()
    supplier_id = uuid4()
    analysis = DeepAnalysis(
        tender_id=tender_id,
        supplier_id=supplier_id,
        compatibility_score=85.5,
        recommendation="Postular",
        justification="Cumple con el 90% de los requisitos y tiene experiencia previa.",
    )
    assert analysis.tender_id == tender_id
    assert analysis.supplier_id == supplier_id
    assert analysis.compatibility_score == 85.5
    assert analysis.recommendation == "Postular"
    assert analysis.justification == "Cumple con el 90% de los requisitos y tiene experiencia previa."
    assert analysis.prompt_instruction is None
    assert isinstance(analysis.created_at, datetime)
    assert isinstance(analysis.updated_at, datetime)
    assert analysis.id is not None


@pytest.mark.parametrize("valid_rec", ["Postular", "Evaluar con cautela", "No recomendado"])
def test_valid_recommendations(valid_rec: str):
    analysis = DeepAnalysis(
        tender_id=uuid4(),
        supplier_id=uuid4(),
        compatibility_score=50.0,
        recommendation=valid_rec,
        justification="Test",
    )
    assert analysis.recommendation == valid_rec


@pytest.mark.parametrize("invalid_rec", ["postular", "Postular ", "Recomendado", "Rechazar", ""])
def test_invalid_recommendations_raises(invalid_rec: str):
    with pytest.raises(ValidationError):
        DeepAnalysis(
            tender_id=uuid4(),
            supplier_id=uuid4(),
            compatibility_score=50.0,
            recommendation=invalid_rec,
            justification="Test",
        )


@pytest.mark.parametrize("invalid_score", [-1.0, 100.1, -0.01, 105.0])
def test_invalid_compatibility_score_raises(invalid_score: float):
    with pytest.raises(ValidationError):
        DeepAnalysis(
            tender_id=uuid4(),
            supplier_id=uuid4(),
            compatibility_score=invalid_score,
            recommendation="Postular",
            justification="Test",
        )
