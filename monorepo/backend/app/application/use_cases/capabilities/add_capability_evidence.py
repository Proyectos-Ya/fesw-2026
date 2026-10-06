from uuid import UUID

from app.application.repositories.capability_repository import (
    ICapabilityAnswerRepository,
    ICapabilityEvidenceRepository,
    ICapabilityQuestionRepository,
)
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.use_cases.capabilities._empresa import empresa_o_error
from app.domain.entities.capability import CapabilityEvidence, evidence_for_answer
from app.domain.errors.capability_errors import (
    CapabilityQuestionNotFound,
    EvidenceNeedsAffirmativeProjectAnswer,
)


class AddCapabilityEvidenceUseCase:
    """Agrega un proyecto que respalda el "Sí" de la empresa activa a una pregunta.

    Es la vía manual: proyectos para clientes privados u otros canales, o para
    corregir lo importado. Las órdenes de compra de Mercado Público no entran por
    acá (plan 230, §5 punto 10).
    """

    def __init__(
        self,
        supplier_repo: ISupplierRepository,
        question_repo: ICapabilityQuestionRepository,
        answer_repo: ICapabilityAnswerRepository,
        evidence_repo: ICapabilityEvidenceRepository,
    ):
        self.supplier_repo = supplier_repo
        self.question_repo = question_repo
        self.answer_repo = answer_repo
        self.evidence_repo = evidence_repo

    async def execute(
        self,
        user_id: UUID,
        supplier_id: UUID | None,
        question_id: UUID,
        title: str,
        year: int,
        buyer: str | None = None,
        amount_clp: int | None = None,
        description: str | None = None,
    ) -> CapabilityEvidence:
        supplier = await empresa_o_error(self.supplier_repo, user_id, supplier_id)

        question = await self.question_repo.get(question_id)
        if question is None:
            raise CapabilityQuestionNotFound(question_id)

        answer = await self.answer_repo.get(supplier.id, question_id)
        if answer is None:
            raise EvidenceNeedsAffirmativeProjectAnswer(None)

        evidence = evidence_for_answer(
            question,
            answer,
            title=title,
            year=year,
            buyer=buyer,
            amount_clp=amount_clp,
            description=description,
            created_by_user_id=user_id,
        )
        return await self.evidence_repo.add(evidence)
