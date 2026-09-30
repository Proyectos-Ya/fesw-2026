from uuid import UUID

from app.application.repositories.proposal_repository import IProposalDraftRepository
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.application.schemas.proposal_schema import ProposalDraftView
from app.application.use_cases.capabilities._empresa import empresa_o_error
from app.domain.errors.proposal_errors import ProposalDraftNotFound
from app.domain.errors.tender_errors import TenderNotFound


class GetProposalUseCase:
    """El borrador de la empresa activa para una licitación, con su vencimiento."""

    def __init__(
        self,
        supplier_repo: ISupplierRepository,
        tender_repo: ITenderRepository,
        draft_repo: IProposalDraftRepository,
    ):
        self.supplier_repo = supplier_repo
        self.tender_repo = tender_repo
        self.draft_repo = draft_repo

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
        return ProposalDraftView(
            **draft.model_dump(), is_expired=tenders[0].esta_cerrada()
        )
