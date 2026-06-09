from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel

from app.domain.entities.tender import Tender
from app.infrastructure.repositories.tender_model import TenderModel, TenderItemModel


class TenderFilters(BaseModel):
    """Filters class to query tenders by multiple dynamic parameters."""
    ids: Optional[List[UUID]] = None
    regions: Optional[List[str]] = None  # Filter by Region Names (e.g. ['Metropolitana'])
    provinces: Optional[List[str]] = None  # Filter by Province Names (e.g. ['Santiago'])


class ITenderRepository(ABC):
    """Interface for the Tender repository in the Application layer."""

    @abstractmethod
    async def get_tenders(self, filters: TenderFilters) -> List[Tender]:
        """Retrieve a list of tenders matching the specified filters."""
        ...

    @abstractmethod
    async def get_by_code(self, code: str) -> Optional[TenderModel]: ...

    @abstractmethod
    async def get_or_create_buyer(self, rut: str, name: str, region_id: int) -> str: ...

    @abstractmethod
    async def save_complex_tender(self, tender_model: TenderModel, items: List[TenderItemModel]) -> None: ...

    @abstractmethod
    async def get_or_create_status(self, status_id: int) -> int: ...

    @abstractmethod
    async def rollback(self) -> None: pass
