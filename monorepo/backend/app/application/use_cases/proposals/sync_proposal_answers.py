from uuid import UUID

from app.application.repositories.proposal_repository import IProposalDraftRepository
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.tender_repository import ITenderRepository
from app.application.use_cases.capabilities.build_experience_catalog import (
    BuildExperienceCatalogUseCase,
)
from app.application.use_cases.proposals._postulacion import (
    postulacion_abierta,
    respuestas_vigentes,
)
from app.application.use_cases.proposals.generate_proposal import (
    GenerateProposalUseCase,
)
from app.domain.entities.proposal import ProposalDraft


class SyncProposalAnswersUseCase:
    """Aplica al borrador las respuestas que la empresa corrigió en el banco.

    Sin rehacer el análisis: las exigencias son las mismas, solo cambia su
    estado. Si el borrador ya tenía texto y se puede redactar, se vuelve a
    redactar con las mismas instrucciones. Si aparece un "No" excluyente, queda
    en pausa como en la factibilidad, sin llamar a la IA. Sin cambios, no hace
    nada.
    """

    def __init__(
        self,
        supplier_repo: ISupplierRepository,
        tender_repo: ITenderRepository,
        draft_repo: IProposalDraftRepository,
        catalog_use_case: BuildExperienceCatalogUseCase,
        generate_use_case: GenerateProposalUseCase,
    ):
        self.supplier_repo = supplier_repo
        self.tender_repo = tender_repo
        self.draft_repo = draft_repo
        self.catalog_use_case = catalog_use_case
        self.generate_use_case = generate_use_case

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
        draft = postulacion.draft
        catalog = await self.catalog_use_case.execute(
            user_id=user_id, supplier_id=postulacion.supplier.id
        )
        vigentes = respuestas_vigentes(draft, catalog)
        if not draft.changed_answers(vigentes):
            return draft

        tenia_texto = draft.content is not None
        draft.sync_answers(
            {question_id: polarity for question_id, (polarity, _) in vigentes.items()}
        )
        draft = await self.draft_repo.save(draft)
        if tenia_texto and draft.can_generate():
            return await self.generate_use_case.execute(
                user_id=user_id,
                supplier_id=postulacion.supplier.id,
                tender_id=tender_id,
                instructions=draft.last_instructions,
            )
        return draft
