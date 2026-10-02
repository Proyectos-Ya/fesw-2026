from uuid import UUID

from app.application.repositories.capability_repository import (
    ICapabilityQuestionRepository,
)
from app.application.repositories.proposal_repository import IProposalDraftRepository
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.tender_repository import ITenderRepository
from app.application.use_cases.capabilities.answer_capability_question import (
    AnswerCapabilityQuestionUseCase,
)
from app.application.use_cases.proposals._postulacion import postulacion_abierta
from app.domain.entities.proposal import ProposalDraft
from app.domain.errors.capability_errors import (
    CapabilityQuestionNotFound,
    InvalidCapabilityAnswer,
)
from app.domain.errors.proposal_errors import QuestionNotInProposal


class AnswerProposalQuestionUseCase:
    """Responde una pregunta de la postulación: banco de la empresa y borrador.

    La respuesta queda en el banco (sirve para las próximas licitaciones) y
    mueve el borrador, que puede pausarse ante un "No" excluyente (CA7). Todo se
    valida contra el borrador **antes** de escribir: una respuesta que el estado
    no admite (por ejemplo otra pregunta mientras hay una pausa) no se guarda en
    ningún lado.
    """

    def __init__(
        self,
        supplier_repo: ISupplierRepository,
        tender_repo: ITenderRepository,
        draft_repo: IProposalDraftRepository,
        question_repo: ICapabilityQuestionRepository,
        answer_use_case: AnswerCapabilityQuestionUseCase,
    ):
        self.supplier_repo = supplier_repo
        self.tender_repo = tender_repo
        self.draft_repo = draft_repo
        self.question_repo = question_repo
        self.answer_use_case = answer_use_case

    async def execute(
        self,
        user_id: UUID,
        supplier_id: UUID | None,
        tender_id: UUID,
        question_id: UUID,
        answer: str,
    ) -> ProposalDraft:
        postulacion = await postulacion_abierta(
            self.supplier_repo,
            self.tender_repo,
            self.draft_repo,
            user_id,
            supplier_id,
            tender_id,
        )
        draft = postulacion.draft
        if not any(r.capability_question_id == question_id for r in draft.requirements):
            raise QuestionNotInProposal(question_id)

        question = await self.question_repo.get(question_id)
        if question is None:
            raise CapabilityQuestionNotFound(question_id)
        polarity = question.polarity_of(answer)
        if polarity is None:
            raise InvalidCapabilityAnswer(question_id, answer)

        # Primero en memoria: si el estado no lo admite, lanza sin escribir nada.
        draft.record_answer(question_id, polarity)

        await self.answer_use_case.execute(
            user_id=user_id,
            supplier_id=postulacion.supplier.id,
            question_id=question_id,
            answer=answer,
            tender_id=tender_id,
        )
        return await self.draft_repo.save(draft)
