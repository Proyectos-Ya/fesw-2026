from app.application.repositories.capability_repository import (
    ICapabilityQuestionRepository,
)
from app.domain.entities.capability import (
    CapabilityQuestion,
    question_leaks_supplier_data,
)
from app.domain.entities.supplier import Supplier
from app.domain.errors.capability_errors import QuestionLeaksSupplierData


class RegisterCapabilityQuestionUseCase:
    """Suma una pregunta al banco compartido. Lo usa la factibilidad de la HU-20 (plan 230, B2).

    La pregunta tiene que salir de lo que exige una licitación, no de los datos
    de la empresa que la origina: la ven todas las demás. Si la nombra, se
    rechaza. Un duplicado de categoría y campo lanza `DuplicateCapabilityQuestion`
    con la pregunta existente, para que el llamador la reuse.
    """

    def __init__(self, question_repo: ICapabilityQuestionRepository):
        self.question_repo = question_repo

    async def execute(
        self, question: CapabilityQuestion, origin_supplier: Supplier | None
    ) -> CapabilityQuestion:
        if origin_supplier is not None and question_leaks_supplier_data(
            question.question, origin_supplier
        ):
            raise QuestionLeaksSupplierData()
        return await self.question_repo.add(question)
