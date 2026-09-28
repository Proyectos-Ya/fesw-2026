"""Dobles para las exportaciones de licitaciones (HdU 19)."""

from uuid import UUID, uuid4

from app.domain.entities.quotation import Quotation, QuotationInput
from app.shared.datetime_utils import utc_now_naive


class InMemoryQuotationRepository:
    def __init__(self) -> None:
        self.quotations: dict[tuple[UUID, UUID], Quotation] = {}

    async def get(self, supplier_id: UUID, tender_id: UUID) -> Quotation | None:
        return self.quotations.get((supplier_id, tender_id))

    async def save(self, supplier_id: UUID, tender_id: UUID, data: QuotationInput) -> Quotation:
        guardada = Quotation(
            id=uuid4(),
            supplier_id=supplier_id,
            tender_id=tender_id,
            currency=data.currency,
            items=data.items,
            updated_at=utc_now_naive(),
        )
        self.quotations[(supplier_id, tender_id)] = guardada
        return guardada
