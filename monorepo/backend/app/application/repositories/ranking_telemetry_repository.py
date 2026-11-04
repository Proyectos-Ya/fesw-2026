from abc import ABC, abstractmethod
from collections.abc import Collection, Sequence
from datetime import date, datetime
from uuid import UUID

from app.domain.entities.ranking_telemetry import (
    AttachmentPriorityShadow,
    PurgeCounts,
    RankingImpression,
    RankingMetricDaily,
    TenderInteraction,
)


class IRankingTelemetryRepository(ABC):
    """Puerto de la telemetría del ranking (plan 233, decisión 8).

    Impresiones servidas, interacciones, NDCG diario y prioridad de anexos en
    sombra. Las consultas de la prioridad y la purga viven acá y no en
    `ITenderRepository`: agregar un método abstracto a esa interfaz obliga a
    implementarlo en todos sus dobles.
    """

    @abstractmethod
    async def save_impressions(self, impressions: list[RankingImpression]) -> None:
        """Guarda las posiciones servidas; idempotente por (ranking_id, position)."""

    @abstractmethod
    async def find_impression(
        self, ranking_id: UUID, tender_id: UUID
    ) -> RankingImpression | None:
        """La posición servida de esa licitación en ese ranking, si existe."""

    @abstractmethod
    async def save_interaction(self, interaction: TenderInteraction) -> bool:
        """Guarda una interacción.

        Devuelve True si se insertó y False si ya existía una con la misma
        (ranking_id, tender_id, kind). Lanza `TenderNotFound` si la licitación no
        existe.
        """

    @abstractmethod
    async def list_impressions_between(
        self, start: datetime, end: datetime
    ) -> list[RankingImpression]:
        """Las impresiones servidas en [start, end), en UTC naive."""

    @abstractmethod
    async def list_attributed_interactions(
        self, ranking_ids: Sequence[UUID]
    ) -> list[TenderInteraction]:
        """Las interacciones atribuidas a alguno de esos rankings."""

    @abstractmethod
    async def upsert_daily_metric(self, metric: RankingMetricDaily) -> None:
        """Inserta la métrica del día y versión, o reemplaza la que ya había."""

    @abstractmethod
    async def list_daily_metrics(
        self, model_version: str | None = None, since_day: date | None = None
    ) -> list[RankingMetricDaily]:
        """Las métricas diarias registradas, ordenadas por (day DESC, model_version)."""

    @abstractmethod
    async def count_top_impressions_by_tender(
        self, since: datetime, max_position: int
    ) -> dict[UUID, int]:
        """Impresiones mostradas (`kind='impresion'`) en posición <= max_position desde `since`."""

    @abstractmethod
    async def count_interactions_by_tender(self, since: datetime) -> dict[UUID, int]:
        """Interacciones desde `since`, sin contar las impresiones."""

    @abstractmethod
    async def tenders_with_manual_upload(self, since: datetime) -> set[UUID]:
        """Licitaciones a las que un usuario subió un documento desde `since`."""

    @abstractmethod
    async def open_tenders_closing_after(
        self, tender_ids: Collection[UUID], min_closing_at: datetime
    ) -> dict[UUID, datetime]:
        """De esas licitaciones, las publicadas que cierran después de `min_closing_at`."""

    @abstractmethod
    async def save_priority_snapshots(
        self, snapshots: list[AttachmentPriorityShadow]
    ) -> None:
        """Guarda la foto de la prioridad en sombra."""

    @abstractmethod
    async def purge_before(self, cutoff: datetime) -> PurgeCounts:
        """Borra lo crudo anterior a `cutoff` (impresiones, interacciones, snapshots).

        Las métricas diarias son agregados sin datos personales y se conservan.
        """
