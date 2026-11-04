"""Interfaz abstracta del repositorio de matching en sombra (Plan 233, Decisión 9)."""

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.matching_shadow import MatchingShadowScore, TenderAttachmentItem


class IMatchingShadowRepository(ABC):
    @abstractmethod
    async def save_shadow_scores(self, scores: list[MatchingShadowScore]) -> None:
        """Guarda en lote los puntajes en sombra calculados."""
        ...

    @abstractmethod
    async def get_shadow_scores_by_ranking(
        self, ranking_id: UUID
    ) -> list[MatchingShadowScore]:
        """Obtiene los puntajes en sombra asociados a un ranking servido."""
        ...

    @abstractmethod
    async def get_shadow_scores_by_supplier(
        self, supplier_id: UUID, variant: str = "att-text-v1", limit: int = 50
    ) -> list[MatchingShadowScore]:
        """Obtiene los últimos puntajes en sombra para un proveedor."""
        ...

    @abstractmethod
    async def save_attachment_items(self, items: list[TenderAttachmentItem]) -> None:
        """Persiste pseudo-partidas extraídas de anexos oficiales."""
        ...

    @abstractmethod
    async def get_attachment_items(self, tender_id: UUID) -> list[TenderAttachmentItem]:
        """Obtiene las pseudo-partidas de una licitación."""
        ...
