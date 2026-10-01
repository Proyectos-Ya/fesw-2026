from uuid import UUID

from app.application.repositories.capability_repository import (
    ICapabilityQuestionRepository,
)
from app.application.repositories.proposal_repository import IProposalDraftRepository
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.application.schemas.proposal_schema import ProposalDraftView
from app.application.use_cases.capabilities._empresa import empresa_o_error
from app.application.use_cases.capabilities.build_experience_catalog import (
    BuildExperienceCatalogUseCase,
)
from app.domain.errors.proposal_errors import ProposalDraftNotFound
from app.domain.errors.tender_errors import TenderNotFound


class GetProposalUseCase:
    """El borrador de la empresa activa para una licitación, listo para mostrar.

    Además del borrador trae lo que la pantalla necesita para no pedir nada más:
    las preguntas a las que apuntan las exigencias (enunciado y opciones) y los
    elementos del catálogo que las cubren, con los que se explica el origen de
    una pausa ("respondiste 'No' el 12-oct en otra licitación").
    """

    def __init__(
        self,
        supplier_repo: ISupplierRepository,
        tender_repo: ITenderRepository,
        draft_repo: IProposalDraftRepository,
        question_repo: ICapabilityQuestionRepository,
        catalog_use_case: BuildExperienceCatalogUseCase,
    ):
        self.supplier_repo = supplier_repo
        self.tender_repo = tender_repo
        self.draft_repo = draft_repo
        self.question_repo = question_repo
        self.catalog_use_case = catalog_use_case

    async def execute(
        self, user_id: UUID, supplier_id: UUID | None, tender_id: UUID
    ) -> ProposalDraftView:
        supplier = await empresa_o_error(self.supplier_repo, user_id, supplier_id)
        tenders = await self.tender_repo.get_tenders(TenderFilters(ids=[tender_id]))
        if not tenders:
            raise TenderNotFound(tender_id)
        draft = await self.draft_repo.get(supplier.id, tender_id)
        if draft is None:
            raise ProposalDraftNotFound(tender_id)

        question_ids = list(
            dict.fromkeys(
                r.capability_question_id
                for r in draft.requirements
                if r.capability_question_id is not None
            )
        )
        questions = (
            await self.question_repo.list_by_ids(question_ids) if question_ids else []
        )
        item_ids = {r.catalog_item_id for r in draft.requirements if r.catalog_item_id}
        catalog_items = []
        if item_ids:
            catalog = await self.catalog_use_case.execute(
                user_id=user_id, supplier_id=supplier.id
            )
            catalog_items = [i for i in catalog.items if i.id in item_ids]

        return ProposalDraftView(
            **draft.model_dump(),
            is_expired=tenders[0].esta_cerrada(),
            questions=questions,
            catalog_items=catalog_items,
        )
