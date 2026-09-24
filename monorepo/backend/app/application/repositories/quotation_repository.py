from typing import Protocol
from uuid import UUID

from app.domain.entities.quotation import Quotation, QuotationInput


class IQuotationRepository(Protocol):
    async def get(self, supplier_id: UUID, tender_id: UUID) -> Quotation | None: ...

    async def save(
        self, supplier_id: UUID, tender_id: UUID, data: QuotationInput
    ) -> Quotation: ...
