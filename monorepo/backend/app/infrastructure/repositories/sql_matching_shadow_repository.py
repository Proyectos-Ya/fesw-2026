"""Implementación SQL del repositorio de matching en sombra (Plan 233, Decisión 9)."""

from uuid import UUID
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.matching_shadow_repository import (
    IMatchingShadowRepository,
)
from app.domain.entities.matching_shadow import (
    MatchingShadowScore,
    TenderAttachmentItem,
)
from app.infrastructure.repositories.matching_shadow_model import (
    MatchingShadowScoreModel,
    TenderAttachmentItemModel,
)


class SqlMatchingShadowRepository(IMatchingShadowRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_shadow_scores(self, scores: list[MatchingShadowScore]) -> None:
        if not scores:
            return
        for s in scores:
            model = MatchingShadowScoreModel(
                id=s.id,
                ranking_id=s.ranking_id,
                supplier_id=s.supplier_id,
                tender_id=s.tender_id,
                variant=s.variant,
                baseline_score=s.baseline_score,
                shadow_score=s.shadow_score,
                reranker_score=s.reranker_score,
                best_match=s.best_match,
                coverage=s.coverage,
                model_version=s.model_version,
                calculated_at=s.calculated_at,
            )
            await self.session.merge(model)
        await self.session.commit()

    async def get_shadow_scores_by_ranking(
        self, ranking_id: UUID
    ) -> list[MatchingShadowScore]:
        query = select(MatchingShadowScoreModel).where(
            MatchingShadowScoreModel.ranking_id == ranking_id
        )
        res = await self.session.exec(query)
        rows = res.all()
        return [
            MatchingShadowScore(
                id=r.id,
                ranking_id=r.ranking_id,
                supplier_id=r.supplier_id,
                tender_id=r.tender_id,
                variant=r.variant,  # type: ignore
                baseline_score=r.baseline_score,
                shadow_score=r.shadow_score,
                reranker_score=r.reranker_score,
                best_match=r.best_match,
                coverage=r.coverage,
                model_version=r.model_version,
                calculated_at=r.calculated_at,
            )
            for r in rows
        ]

    async def get_shadow_scores_by_supplier(
        self, supplier_id: UUID, variant: str = "att-text-v1", limit: int = 50
    ) -> list[MatchingShadowScore]:
        query = (
            select(MatchingShadowScoreModel)
            .where(
                MatchingShadowScoreModel.supplier_id == supplier_id,
                MatchingShadowScoreModel.variant == variant,
            )
            .order_by(MatchingShadowScoreModel.calculated_at.desc())
            .limit(limit)
        )
        res = await self.session.exec(query)
        rows = res.all()
        return [
            MatchingShadowScore(
                id=r.id,
                ranking_id=r.ranking_id,
                supplier_id=r.supplier_id,
                tender_id=r.tender_id,
                variant=r.variant,  # type: ignore
                baseline_score=r.baseline_score,
                shadow_score=r.shadow_score,
                reranker_score=r.reranker_score,
                best_match=r.best_match,
                coverage=r.coverage,
                model_version=r.model_version,
                calculated_at=r.calculated_at,
            )
            for r in rows
        ]

    async def save_attachment_items(self, items: list[TenderAttachmentItem]) -> None:
        if not items:
            return
        for item in items:
            model = TenderAttachmentItemModel(
                id=item.id,
                tender_id=item.tender_id,
                title=item.title,
                description=item.description,
                quantity=item.quantity,
                unit=item.unit,
                created_at=item.created_at,
            )
            await self.session.merge(model)
        await self.session.commit()

    async def get_attachment_items(self, tender_id: UUID) -> list[TenderAttachmentItem]:
        query = select(TenderAttachmentItemModel).where(
            TenderAttachmentItemModel.tender_id == tender_id
        )
        res = await self.session.exec(query)
        rows = res.all()
        return [
            TenderAttachmentItem(
                id=r.id,
                tender_id=r.tender_id,
                title=r.title,
                description=r.description,
                quantity=r.quantity,
                unit=r.unit,
                created_at=r.created_at,
            )
            for r in rows
        ]
