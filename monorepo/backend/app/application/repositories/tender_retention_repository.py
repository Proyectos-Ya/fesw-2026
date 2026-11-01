"""Retención de licitaciones cerradas que nadie usó (plan 306)."""

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID


class ITenderRetentionRepository(ABC):
    """Elige y borra las licitaciones que ya no vale la pena guardar.

    Una licitación es borrable si no está activa, cerró antes de `corte` y no
    tiene filas en ninguna tabla de uso (guardada, kanban, hitos, cotización,
    chat, borrador, link compartido, archivos subidos, etc.).
    """

    @abstractmethod
    async def ids_borrables(self, corte: datetime, limite: int) -> list[UUID]:
        """Hasta `limite` ids borrables, las que cerraron antes primero."""
        ...

    @abstractmethod
    async def borrar(self, tender_ids: list[UUID], corte: datetime) -> int:
        """Borra las de `tender_ids` que sigan siendo borrables y cuenta cuántas.

        Vuelve a revisar las condiciones dentro de la transacción: una que
        alguien usó después de `ids_borrables` se conserva entera, con sus
        partidas. Todo el lote va en una sola transacción.
        """
        ...
