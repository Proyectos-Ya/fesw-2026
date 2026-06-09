from abc import ABC, abstractmethod
from uuid import UUID


class IRerankerService(ABC):
    """
    Interfaz abstracta para el servicio de re-ranking (cross-encoder).
    """

    @abstractmethod
    async def rerank(
        self,
        query_text: str,
        candidates: list[tuple[UUID, str]],
        limit: int,
    ) -> list[tuple[UUID, float]]:
        """
        Ordena un listado de candidatos en base a su afinidad semántica con el texto de consulta (query_text).

        Retorna los top 'limit' candidatos ordenados de mayor a menor score, como tuplas de (tender_id, score).
        """
        ...
