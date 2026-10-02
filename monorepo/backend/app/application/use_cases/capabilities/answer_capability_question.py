from datetime import datetime
from uuid import UUID

from app.application.repositories.capability_repository import (
    ICapabilityAnswerRepository,
    ICapabilityQuestionRepository,
)
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.use_cases.capabilities._empresa import empresa_o_error
from app.domain.entities.capability import CapabilityAnswer
from app.domain.errors.capability_errors import (
    CapabilityQuestionNotFound,
    InvalidCapabilityAnswer,
)
from app.shared.datetime_utils import utc_now_naive


class AnswerCapabilityQuestionUseCase:
    """Guarda la respuesta de la empresa activa a una pregunta del banco.

    La respuesta es de la empresa: cualquier miembro puede darla o corregirla, y
    queda registrado quién fue. **No** se copia a `supplier.keywords` ni a
    `certifications`; llevarla al matching es otra issue (plan 230, §5).

    La empresa sale de la sesión (`WorkspaceContext`), nunca de un id del
    cliente: con un `supplier_id` en el cuerpo, cualquiera que conociera el de
    otra empresa podría escribir en su banco.
    """

    def __init__(
        self,
        supplier_repo: ISupplierRepository,
        question_repo: ICapabilityQuestionRepository,
        answer_repo: ICapabilityAnswerRepository,
    ):
        self.supplier_repo = supplier_repo
        self.question_repo = question_repo
        self.answer_repo = answer_repo

    async def execute(
        self,
        user_id: UUID,
        supplier_id: UUID | None,
        question_id: UUID,
        answer: str,
        valid_until: datetime | None = None,
        tender_id: UUID | None = None,
    ) -> CapabilityAnswer:
        supplier = await empresa_o_error(self.supplier_repo, user_id, supplier_id)

        question = await self.question_repo.get(question_id)
        if question is None:
            raise CapabilityQuestionNotFound(question_id)
        if not question.accepts(answer):
            raise InvalidCapabilityAnswer(question_id, answer)

        # Corregir una respuesta no cambia la licitación que motivó la pregunta.
        previa = await self.answer_repo.get(supplier.id, question_id)
        origen = previa.tender_id if previa and previa.tender_id else tender_id
        return await self.answer_repo.save(
            CapabilityAnswer(
                supplier_id=supplier.id,
                question_id=question_id,
                answer=answer,
                answered=True,
                omitted=False,
                tender_id=origen,
                answered_by_user_id=user_id,
                valid_until=valid_until,
                answered_at=utc_now_naive(),
            )
        )
