from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class FiltrosVectoriales:
    region: str | None = None
    monto_min: float | None = None


@dataclass(frozen=True)
class VectorSearchResult:
    licitacion_id: UUID
    score: float


class IVectorStoreService(ABC):

    @abstractmethod
    async def ensure_collection(self) -> None: ...

    @abstractmethod
    async def upsert(
        self,
        vector_id: UUID,
        vector: list[float],
        payload: dict[str, str | float | None],
    ) -> None: ...

    @abstractmethod
    async def search(
        self,
        query_vector: list[float],
        top_k: int,
        filtros: FiltrosVectoriales | None = None,
    ) -> list[VectorSearchResult]: ...
