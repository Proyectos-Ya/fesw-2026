from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.entities.deep_analysis import DeepAnalysis, RecommendationLiteral


def test_create_valid_deep_analysis():
    """Verifica que se pueda crear una instancia válida de DeepAnalysis con todos los campos requeridos."""
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
    assert (
        analysis.justification
        == "Cumple con el 90% de los requisitos y tiene experiencia previa."
    )
    assert analysis.prompt_instruction is None
    assert isinstance(analysis.created_at, datetime)
    assert isinstance(analysis.updated_at, datetime)
    assert analysis.id is not None


@pytest.mark.parametrize(
    "valid_rec", ["Postular", "Evaluar con cautela", "No recomendado"]
)
def test_valid_recommendations(valid_rec: RecommendationLiteral):
    """Verifica que la entidad acepte los tres valores válidos para la recomendación."""
    analysis = DeepAnalysis(
        tender_id=uuid4(),
        supplier_id=uuid4(),
        compatibility_score=50.0,
        recommendation=valid_rec,
        justification="Test",
    )
    assert analysis.recommendation == valid_rec


@pytest.mark.parametrize(
    "invalid_rec", ["postular", "Postular ", "Recomendado", "Rechazar", ""]
)
def test_invalid_recommendations_raises(invalid_rec: str):
    """Verifica que se lance un ValidationError si se proporciona una recomendación no válida o mal formateada."""
    with pytest.raises(ValidationError):
        DeepAnalysis(
            tender_id=uuid4(),
            supplier_id=uuid4(),
            compatibility_score=50.0,
            # El valor inválido es justamente lo que se está probando.
            recommendation=invalid_rec,  # type: ignore[arg-type]
            justification="Test",
        )


@pytest.mark.parametrize("invalid_score", [-1.0, 100.1, -0.01, 105.0])
def test_invalid_compatibility_score_raises(invalid_score: float):
    """Verifica que se lance un ValidationError si el porcentaje de compatibilidad está fuera del rango [0.0, 100.0]."""
    with pytest.raises(ValidationError):
        DeepAnalysis(
            tender_id=uuid4(),
            supplier_id=uuid4(),
            compatibility_score=invalid_score,
            recommendation="Postular",
            justification="Test",
        )
