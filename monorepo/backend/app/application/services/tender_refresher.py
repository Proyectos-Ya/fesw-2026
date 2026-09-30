from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class OfficialTenderDates:
    """Fechas oficiales vigentes en Mercado Público, en UTC naive."""

    published_at: datetime
    closing_at: datetime


class ITenderRefresher(ABC):
    @abstractmethod
    async def refresh(self, code: str) -> OfficialTenderDates | None:
        """Vuelve a traer la licitación de Mercado Público y la actualiza en la base.

        Devuelve las fechas vigentes, o None si Mercado Público ya no la entrega.
        Lanza si Mercado Público no respondió.
        """
