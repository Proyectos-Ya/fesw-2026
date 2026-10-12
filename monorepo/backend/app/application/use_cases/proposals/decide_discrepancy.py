from uuid import UUID

from app.application.repositories.proposal_repository import IProposalDraftRepository
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.tender_repository import ITenderRepository
from app.application.use_cases.proposals._postulacion import postulacion_abierta
from app.domain.entities.proposal import DecisionAction, ProposalDraft
from app.domain.errors.proposal_errors import InvalidProposalTransition


class DecideDiscrepancyUseCase:
    """Continuar con advertencia (CA8) o detener (CA9) ante un "No" excluyente.

    Recibe la exigencia sobre la que el usuario decidió. Si la pausa ya es otra
    (otro miembro respondió mientras tanto), no se aplica: decidir "continuar"
    sobre una exigencia que el usuario no vio sería aceptar algo a ciegas.
    """

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
        self,
        user_id: UUID,
        supplier_id: UUID | None,
        tender_id: UUID,
        requirement_id: str,
        action: DecisionAction,
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
        if draft.status == "PAUSED" and draft.paused_requirement_id != requirement_id:
            raise InvalidProposalTransition(
                draft.status, "decidir sobre otra exigencia en"
            )
        draft.decide(action, user_id)
        return await self.draft_repo.save(draft)
