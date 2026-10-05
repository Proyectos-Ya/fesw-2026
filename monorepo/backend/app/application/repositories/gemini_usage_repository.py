"""Puerto para el registro y control de cuota diaria de Gemini (plan 233, decisión 4)."""

from abc import ABC, abstractmethod
from datetime import date


class IGeminiUsageRepository(ABC):
    @abstractmethod
    async def try_reserve_call(self, *, day: date, limit: int) -> bool:
        """Intenta reservar una llamada en el contador diario.

        Incrementa atómicamente si calls < limit. Devuelve True si se reservó,
        o False si se alcanzó el límite.
        """
        ...

    @abstractmethod
    async def add_tokens(
        self, *, day: date, prompt_tokens: int, output_tokens: int
    ) -> None:
        """Acumula tokens consumidos para el día dado."""
        ...

    @abstractmethod
    async def calls_on(self, day: date) -> int:
        """Llamadas registradas para el día dado."""
        ...
