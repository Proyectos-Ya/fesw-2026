from uuid import UUID

from app.application.repositories.capability_repository import (
    ICapabilityAnswerRepository,
    ICapabilityQuestionRepository,
)
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.application.schemas.capability_schema import PendingCapabilityQuestion
from app.application.use_cases.capabilities._empresa import empresa_o_error
from app.shared.datetime_utils import utc_now_naive


class ListPendingCapabilityQuestionsUseCase:
    """Preguntas que la empresa activa tiene por responder.

    Pendiente es lo que no está respondido ni omitido, y también lo respondido
    cuya vigencia venció (una certificación que expiró se vuelve a preguntar).
    Cada una trae la licitación que la originó, si la hay: explica "¿por qué me
    preguntan esto?" sin tener que abrir la postulación.
    """

    def __init__(
        self,
        supplier_repo: ISupplierRepository,
        question_repo: ICapabilityQuestionRepository,
        answer_repo: ICapabilityAnswerRepository,
        tender_repo: ITenderRepository,
    ):
        self.supplier_repo = supplier_repo
        self.question_repo = question_repo
        self.answer_repo = answer_repo
        self.tender_repo = tender_repo

    async def execute(
        self, user_id: UUID, supplier_id: UUID | None
    ) -> list[PendingCapabilityQuestion]:
        supplier = await empresa_o_error(self.supplier_repo, user_id, supplier_id)
        now = utc_now_naive()
        pendientes = [
            a
            for a in await self.answer_repo.list_by_supplier(supplier.id)
            if not a.omitted and not a.is_current(now)
        ]
        if not pendientes:
            return []

        questions = {
            q.id: q
            for q in await self.question_repo.list_by_ids(
                [a.question_id for a in pendientes]
            )
        }
        tender_ids = list({a.tender_id for a in pendientes if a.tender_id})
        tenders = (
            {
                t.id: t
                for t in await self.tender_repo.get_tenders(
                    TenderFilters(ids=tender_ids)
                )
            }
            if tender_ids
            else {}
        )

        resultado: list[PendingCapabilityQuestion] = []
        for answer in sorted(pendientes, key=lambda a: a.generated_at):
            question = questions.get(answer.question_id)
            if question is None:
                continue
            tender = tenders.get(answer.tender_id) if answer.tender_id else None
            resultado.append(
                PendingCapabilityQuestion(
                    question=question,
                    tender_id=answer.tender_id,
                    tender_code=tender.code if tender else None,
                    tender_name=tender.name if tender else None,
                    generated_at=answer.generated_at,
                )
            )
        return resultado
