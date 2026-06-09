from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID


class ITenderVectorRepository(ABC):
    """
    Interfaz abstracta para el repositorio vectorial de licitaciones (tenders).
    """

    @abstractmethod
    async def ensure_collection(self) -> None:
        """
        Asegura que la colección de licitaciones exista en Qdrant.
        """
        ...

    @abstractmethod
    async def upsert(
        self,
        tender_id: UUID,
        embedding: list[float],
        payload: dict,
    ) -> None:
        """
        Crea o actualiza el vector nombrado (named vector) de una licitación en Qdrant.
        """
        ...

    @abstractmethod
    async def delete(self, tender_id: UUID) -> None:
        """
        Elimina el vector de una licitación en Qdrant.
        """
        ...

    @abstractmethod
    async def search_by_supplier_vector(
        self,
        supplier_vector: list[float],
        limit: int,
        filters: Optional[dict] = None,
    ) -> list[tuple[UUID, float]]:
        """
        Busca las top N licitaciones afines al vector de perfil de un proveedor,
        aplicando los filtros de metadatos sobre el payload.

        Devuelve una lista de tuplas (tender_id, similarity_score).
        """
        ...
