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
    async def get_by_supplier_id(self, supplier_id: UUID) -> list[MatchingResult]:
        """Obtiene la lista de resultados de matching asociados a un proveedor."""
        pass

    @abstractmethod
    async def delete_by_supplier_id(self, supplier_id: UUID) -> None:
        """Elimina todos los resultados de matching asociados a un proveedor."""
        pass

    @abstractmethod
    async def get_by_proveedor_and_licitacion(
        self, proveedor_id: UUID, licitacion_id: UUID
    ) -> MatchingResult | None:
        """Obtiene un resultado de matching específico por ID de proveedor y licitación."""
        pass

