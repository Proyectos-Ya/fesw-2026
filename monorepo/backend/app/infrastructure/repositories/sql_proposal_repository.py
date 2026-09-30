from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.proposal_repository import IProposalDraftRepository
from app.domain.entities.proposal import ProposalDraft
from app.infrastructure.repositories.proposal_model import ProposalDraftModel


class SqlProposalDraftRepository(IProposalDraftRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _to_entity(model: ProposalDraftModel) -> ProposalDraft:
        return ProposalDraft.model_validate(model.model_dump())

    @staticmethod
    def _columnas(draft: ProposalDraft) -> dict:
        # `mode="json"` para lo que va a JSONB: UUID y fechas anidadas no son
        # serializables tal cual. Las columnas escalares van en modo Python.
        datos = draft.model_dump(
            exclude={"requirements", "warnings", "discrepancy_decisions", "content"}
        )
        anidados = draft.model_dump(
            mode="json",
            include={"requirements", "warnings", "discrepancy_decisions", "content"},
        )
        return datos | anidados

    async def get(self, supplier_id: UUID, tender_id: UUID) -> ProposalDraft | None:
        result = await self.session.exec(
            select(ProposalDraftModel).where(
                ProposalDraftModel.supplier_id == supplier_id,
                ProposalDraftModel.tender_id == tender_id,
            )
        )
        model = result.first()
        return self._to_entity(model) if model else None

    async def save(self, draft: ProposalDraft) -> ProposalDraft:
        columnas = self._columnas(draft)
        model = await self.session.get(ProposalDraftModel, draft.id)
        if model is None:
            self.session.add(ProposalDraftModel(**columnas))
        else:
            for campo, valor in columnas.items():
                setattr(model, campo, valor)
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return draft
