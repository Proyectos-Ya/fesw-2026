from collections.abc import Collection, Iterator, Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, delete, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.application.repositories.ranking_telemetry_repository import (
    IRankingTelemetryRepository,
)
from app.domain.entities.ranking_telemetry import (
    AttachmentPriorityShadow,
    InteractionKind,
    PurgeCounts,
    RankingImpression,
    RankingMetricDaily,
    TenderInteraction,
)
from app.domain.errors.tender_errors import TenderNotFound
from app.infrastructure.repositories.ranking_telemetry_model import (
    AttachmentPriorityShadowModel,
    RankingImpressionModel,
    RankingMetricDailyModel,
    TenderInteractionModel,
)
from app.infrastructure.repositories.tender_chat_model import TenderChatDocumentModel
from app.infrastructure.repositories.tender_model import TenderModel
from app.shared.constants import PUBLICADA_STATUS_ID

_IMPRESION_UNICA = "uq_ranking_impression_ranking_position"
_INTERACCION_UNICA = "uq_tender_interaction_ranking_tender_kind"
_METRICA_UNICA = "uq_ranking_metric_daily_day_version"

# Tamaño de los lotes de IN (...) e INSERT masivo: lejos del tope de parámetros
# de asyncpg (32.767) incluso con varias columnas por fila.
_LOTE = 1000


def _en_lotes[T](items: Sequence[T], tamano: int = _LOTE) -> Iterator[Sequence[T]]:
    for inicio in range(0, len(items), tamano):
        yield items[inicio : inicio + tamano]


class SqlRankingTelemetryRepository(IRankingTelemetryRepository):
    """Telemetría del ranking sobre PostgreSQL (plan 233, decisión 8)."""

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _impression_to_entity(model: RankingImpressionModel) -> RankingImpression:
        return RankingImpression(
            id=model.id,
            ranking_id=model.ranking_id,
            supplier_id=model.supplier_id,
            user_id=model.user_id,
            tender_id=model.tender_id,
            position=model.position,
            score=model.score,
            model_version=model.model_version,
            created_at=model.created_at,
        )

    @staticmethod
    def _interaction_to_entity(model: TenderInteractionModel) -> TenderInteraction:
        return TenderInteraction(
            id=model.id,
            user_id=model.user_id,
            supplier_id=model.supplier_id,
            tender_id=model.tender_id,
            kind=InteractionKind(model.kind),
            ranking_id=model.ranking_id,
            position=model.position,
            source=model.source,  # type: ignore[arg-type]
            created_at=model.created_at,
        )

    async def save_impressions(self, impressions: list[RankingImpression]) -> None:
        if not impressions:
            return
        for lote in _en_lotes(impressions):
            stmt = (
                pg_insert(RankingImpressionModel)
                .values([i.model_dump() for i in lote])
                .on_conflict_do_nothing(constraint=_IMPRESION_UNICA)
            )
            await self.session.exec(stmt)  # type: ignore[call-overload]
        await self.session.commit()

    async def find_impression(
        self, ranking_id: UUID, tender_id: UUID
    ) -> RankingImpression | None:
        result = await self.session.exec(
            select(RankingImpressionModel).where(
                RankingImpressionModel.ranking_id == ranking_id,
                RankingImpressionModel.tender_id == tender_id,
            )
        )
        model = result.first()
        return self._impression_to_entity(model) if model else None

    async def save_interaction(self, interaction: TenderInteraction) -> bool:
        fila = {**interaction.model_dump(), "kind": interaction.kind.value}
        stmt = (
            pg_insert(TenderInteractionModel)
            .values(**fila)
            .on_conflict_do_nothing(constraint=_INTERACCION_UNICA)
            .returning(TenderInteractionModel.id)
        )
        try:
            result = await self.session.exec(stmt)  # type: ignore[call-overload]
            inserted = len(result.all()) == 1
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            # Lo único que puede violarse además del índice único, que absorbe
            # ON CONFLICT, es una FK. Usuario y empresa salen de la sesión
            # autenticada, así que la que falla es la licitación.
            raise TenderNotFound(interaction.tender_id) from exc
        return inserted

    async def list_impressions_between(
        self, start: datetime, end: datetime
    ) -> list[RankingImpression]:
        result = await self.session.exec(
            select(RankingImpressionModel).where(
                col(RankingImpressionModel.created_at) >= start,
                col(RankingImpressionModel.created_at) < end,
            )
        )
        return [self._impression_to_entity(m) for m in result.all()]

    async def list_attributed_interactions(
        self, ranking_ids: Sequence[UUID]
    ) -> list[TenderInteraction]:
        interactions: list[TenderInteraction] = []
        for lote in _en_lotes(list(ranking_ids)):
            result = await self.session.exec(
                select(TenderInteractionModel).where(
                    col(TenderInteractionModel.ranking_id).in_(lote)
                )
            )
            interactions.extend(self._interaction_to_entity(m) for m in result.all())
        return interactions

    async def upsert_daily_metric(self, metric: RankingMetricDaily) -> None:
        stmt = pg_insert(RankingMetricDailyModel).values(**metric.model_dump())
        stmt = stmt.on_conflict_do_update(
            constraint=_METRICA_UNICA,
            set_={
                columna: stmt.excluded[columna]
                for columna in (
                    "ndcg_at_10",
                    "ci_low",
                    "ci_high",
                    "rankings_evaluated",
                    "rankings_served",
                    "computed_at",
                )
            },
        )
        await self.session.exec(stmt)  # type: ignore[call-overload]
        await self.session.commit()

    async def count_top_impressions_by_tender(
        self, since: datetime, max_position: int
    ) -> dict[UUID, int]:
        # La comparación con NULL ya deja fuera las filas sin posición.
        result = await self.session.exec(
            select(TenderInteractionModel.tender_id, func.count())
            .where(
                col(TenderInteractionModel.kind) == InteractionKind.IMPRESION.value,
                col(TenderInteractionModel.position) <= max_position,
                col(TenderInteractionModel.created_at) >= since,
            )
            .group_by(col(TenderInteractionModel.tender_id))
        )
        return {tender_id: total for tender_id, total in result.all()}

    async def count_interactions_by_tender(self, since: datetime) -> dict[UUID, int]:
        result = await self.session.exec(
            select(TenderInteractionModel.tender_id, func.count())
            .where(
                col(TenderInteractionModel.kind) != InteractionKind.IMPRESION.value,
                col(TenderInteractionModel.created_at) >= since,
            )
            .group_by(col(TenderInteractionModel.tender_id))
        )
        return {tender_id: total for tender_id, total in result.all()}

    async def tenders_with_manual_upload(self, since: datetime) -> set[UUID]:
        # Hoy una subida manual es un documento del chat de la licitación; con la
        # decisión 2 pasa a leer la tabla de anexos.
        result = await self.session.exec(
            select(TenderChatDocumentModel.tender_id)
            .where(col(TenderChatDocumentModel.created_at) >= since)
            .distinct()
        )
        return set(result.all())

    async def open_tenders_closing_after(
        self, tender_ids: Collection[UUID], min_closing_at: datetime
    ) -> dict[UUID, datetime]:
        abiertas: dict[UUID, datetime] = {}
        for lote in _en_lotes(list(tender_ids)):
            result = await self.session.exec(
                select(TenderModel.id, TenderModel.closing_at).where(
                    col(TenderModel.id).in_(lote),
                    col(TenderModel.status_id) == PUBLICADA_STATUS_ID,
                    col(TenderModel.closing_at) > min_closing_at,
                )
            )
            abiertas.update({tender_id: closing for tender_id, closing in result.all()})
        return abiertas

    async def save_priority_snapshots(
        self, snapshots: list[AttachmentPriorityShadow]
    ) -> None:
        if not snapshots:
            return
        for lote in _en_lotes(snapshots):
            stmt = pg_insert(AttachmentPriorityShadowModel).values(
                [s.model_dump() for s in lote]
            )
            await self.session.exec(stmt)  # type: ignore[call-overload]
        await self.session.commit()

    async def purge_before(self, cutoff: datetime) -> PurgeCounts:
        impressions = await self.session.exec(  # type: ignore[call-overload]
            delete(RankingImpressionModel).where(
                col(RankingImpressionModel.created_at) < cutoff
            )
        )
        interactions = await self.session.exec(  # type: ignore[call-overload]
            delete(TenderInteractionModel).where(
                col(TenderInteractionModel.created_at) < cutoff
            )
        )
        snapshots = await self.session.exec(  # type: ignore[call-overload]
            delete(AttachmentPriorityShadowModel).where(
                col(AttachmentPriorityShadowModel.computed_at) < cutoff
            )
        )
        await self.session.commit()
        return PurgeCounts(
            impressions=impressions.rowcount or 0,
            interactions=interactions.rowcount or 0,
            priority_snapshots=snapshots.rowcount or 0,
        )
