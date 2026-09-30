from uuid import UUID

from app.application.repositories.proposal_repository import IProposalDraftRepository
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.tender_repository import ITenderRepository
from app.application.use_cases.proposals._postulacion import postulacion_abierta
from app.domain.entities.proposal import ProposalDraft


class ResumeProposalUseCase:
    """Reanuda una postulación detenida (CA9): vuelve a factibilidad para corregir."""

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
    ) -> ProposalDraft:
        postulacion = await postulacion_abierta(
            self.supplier_repo,
            self.tender_repo,
            self.draft_repo,
            user_id,
            supplier_id,
            tender_id,
        )
        postulacion.draft.resume()
        return await self.draft_repo.save(postulacion.draft)
