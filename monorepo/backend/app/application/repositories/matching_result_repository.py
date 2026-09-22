from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.matching_result import MatchingResult


class IMatchingResultRepository(ABC):
    """Interfaz abstracta para el repositorio de persistencia de resultados de matching (caching de recomendaciones)."""

    @abstractmethod
    async def save_bulk(self, results: list[MatchingResult]) -> None:
        """Guarda en lote una lista de resultados de matching."""
        pass

    @abstractmethod
    async def save_on_demand(self, result: MatchingResult) -> MatchingResult:
        """Guarda un cálculo pedido por el usuario, reemplazando el anterior del par.

        Va aparte de `save_bulk` porque no puede acumular filas: hay una
        restricción única por (proveedor, licitación), y recalcular a pedido
        significa sustituir el valor previo, no agregar otro.
        """
        pass

    @abstractmethod
    async def get_by_supplier_id(self, supplier_id: UUID) -> list[MatchingResult]:
        """Obtiene todos los resultados de un proveedor, sin importar su origen."""
        pass

    @abstractmethod
    async def get_ranking_by_supplier_id(
        self, supplier_id: UUID
    ) -> list[MatchingResult]:
        """Obtiene solo las filas del ranking: son las que forman las recomendaciones.

        Los cálculos a pedido no son recomendaciones —el sistema nunca las
        propuso— así que quedan fuera del dashboard y de las alertas.
        """
        pass

    @abstractmethod
    async def delete_by_supplier_id(self, supplier_id: UUID) -> None:
        """Elimina todos los resultados de matching asociados a un proveedor."""
        pass

    @abstractmethod
    async def delete_ranking_by_supplier_id(self, supplier_id: UUID) -> None:
        """Elimina solo las filas del ranking, preservando los cálculos a pedido."""
        pass

    @abstractmethod
    async def delete_by_supplier_and_tender_ids(
        self, supplier_id: UUID, tender_ids: list[UUID]
    ) -> None:
        """Elimina las filas del proveedor para esas licitaciones, sea cual sea su origen.

        La usa el ranking antes de insertar: si una licitación calculada a
        pedido entra al top, su fila vieja tiene que salir o choca con la
        restricción única.
        """
        pass

    @abstractmethod
    async def get_by_proveedor_and_licitacion(
        self, proveedor_id: UUID, licitacion_id: UUID
    ) -> MatchingResult | None:
        """Obtiene un resultado de matching específico por ID de proveedor y licitación."""
        pass
