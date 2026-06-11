from uuid import uuid4
import pytest

from app.application.use_cases.questions.answer_question_use_case import AnswerQuestionUseCase
from app.domain.entities.supplier import Supplier
from tests.unit.application.fakes import InMemorySupplierRepository

VALID_RUT = "76086428-5"

@pytest.fixture
def supplier_repo() -> InMemorySupplierRepository:
    """Fixture que provee el repositorio en memoria nativo del proyecto."""
    return InMemorySupplierRepository()


@pytest.fixture
def use_case(supplier_repo: InMemorySupplierRepository) -> AnswerQuestionUseCase:
    """Fixture que inicializa el caso de uso con el repositorio en memoria."""
    return AnswerQuestionUseCase(supplier_repo=supplier_repo)


@pytest.mark.asyncio
async def test_answer_question_updates_keywords_successfully(
    use_case: AnswerQuestionUseCase, 
    supplier_repo: InMemorySupplierRepository
) -> None:
    """Verifica que al responder una pregunta, la respuesta se guarde en las keywords del supplier."""
    supplier_id = uuid4()
    supplier = Supplier(
        id=supplier_id,
        rut=VALID_RUT,
        legal_name="Empresa Test SpA",
        keywords=[],  # Inicialmente vacío
    )
    await supplier_repo.save(supplier)

    await use_case.execute(
        supplier_id=supplier_id,
        field_name="bim_capabilities",
        answer="Sí, nivel básico/intermedio"
    )

    updated_supplier = await supplier_repo.get_by_id(supplier_id)
    
    assert updated_supplier is not None
    keywords_actuales = updated_supplier.keywords or []
    assert "bim_capabilities:Sí, nivel básico/intermedio" in keywords_actuales