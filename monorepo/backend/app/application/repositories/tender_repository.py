from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.application.schemas.tender_schema import TenderFilterCriteria
from app.domain.entities.deep_analysis import DeepAnalysis
from app.domain.entities.tender import Tender

# DEUDA (dirección de dependencias): la capa de aplicación no debería conocer
# infraestructura. `get_by_code` y `save_complex_tender` exponen modelos de
# SQLModel en una interfaz abstracta, lo que ata cualquier implementación futura
# a ese ORM. Desenredarlo obliga a tocar la ingesta completa, así que se deja
# anotado. **Los métodos nuevos deben hablar solo de entidades de dominio.**
from app.infrastructure.repositories.tender_model import TenderItemModel, TenderModel


class TenderFilters(BaseModel):
    """Filters class to query tenders by multiple dynamic parameters."""

    ids: list[UUID] | None = None
    regions: list[str] | None = None  # Filter by Region Names (e.g. ['Metropolitana'])


class ITenderRepository(ABC):
    """Interface for the Tender repository in the Application layer."""

    @abstractmethod
    async def get_tenders(self, filters: TenderFilters) -> list[Tender]:
        """Retrieve a list of tenders matching the specified filters."""
        ...

    @abstractmethod
    async def search_tenders(
        self,
        criteria: TenderFilterCriteria,
        limit: int,
        offset: int = 0,
    ) -> tuple[list[Tender], int]:
        """Busca licitaciones por filtros, ordenadas por fecha de cierre.

        Respaldo del buscador manual para cuando no hay vector con que ordenar
        por relevancia: proveedor recién registrado o perfil sin completar.

        Devuelve `(licitaciones de esta página, total que cumple los filtros)`.
        El total es independiente del corte, igual que en el camino vectorial.
        """
        ...

    @abstractmethod
    async def get_by_code(self, code: str) -> TenderModel | None: ...

    @abstractmethod
    async def get_expired_published_ids(self) -> list[UUID]:
        """Ids de las licitaciones que siguen figurando publicadas pero ya cerraron.

        Solo las que dicen `publicada`: una cancelada o desierta con el plazo
        vencido no se reabre ni se reescribe.
        """
        ...

    @abstractmethod
    async def mark_as_closed(self, tender_ids: list[UUID]) -> None:
        """Pasa esas licitaciones al estado `cerrada`, en una sola sentencia."""
        ...

    @abstractmethod
    async def get_or_create_buyer(
        self,
        rut: str,
        name: str,
        region_id: int,
        comuna_id: int | None = None,
        comuna_resolution_source: str | None = None,
    ) -> str: ...

    @abstractmethod
    async def get_comuna_id_by_name(self, name: str) -> int | None: ...

    @abstractmethod
    async def get_provincia_id_by_comuna_id(self, comuna_id: int) -> int | None: ...

    @abstractmethod
    async def save_complex_tender(
        self, tender_model: TenderModel, items: list[TenderItemModel]
    ) -> None: ...

    @abstractmethod
    async def get_or_create_status(self, status_id: int, code: str) -> int: ...

    @abstractmethod
    async def rollback(self) -> None:
        pass

    @abstractmethod
    async def get_deep_analysis(
        self, tender_id: UUID, supplier_id: UUID
    ) -> DeepAnalysis | None:
        """Retrieve the DeepAnalysis for a specific tender and supplier, if it exists."""
        ...

    @abstractmethod
    async def save_deep_analysis(self, deep_analysis: DeepAnalysis) -> DeepAnalysis:
        """Save (create or update) the DeepAnalysis in the database."""
        ...

    @abstractmethod
    async def get_latest_tender_created_at(self) -> datetime | None:
        """Retrieve the timestamp of the most recently created tender."""
        ...
