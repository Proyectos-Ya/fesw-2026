from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel

from app.domain.entities.tender import Tender


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
