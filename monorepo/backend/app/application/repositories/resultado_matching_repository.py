from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.resultado_matching import ResultadoMatching


class IResultadoMatchingRepository(ABC):

    @abstractmethod
    async def save_bulk(self, resultados: list[ResultadoMatching]) -> None: ...

    @abstractmethod
    async def get_by_proveedor_and_licitacion(
        self,
        proveedor_id: UUID,
        licitacion_id: UUID,
    ) -> ResultadoMatching | None: ...
