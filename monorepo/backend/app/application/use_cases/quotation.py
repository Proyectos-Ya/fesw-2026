from uuid import UUID

from app.application.repositories.quotation_repository import IQuotationRepository
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.repositories.tender_repository import (
    ITenderRepository,
    TenderFilters,
)
from app.application.use_cases.supplier.resolver_empresa import resolver_empresa
from app.domain.entities.quotation import Quotation, QuotationInput
from app.domain.errors.tender_errors import TenderNotFound


class QuotationNotFound(Exception):
    pass


class QuotationCompanyRequired(Exception):
    pass


class QuotationUseCase:
    def __init__(
        self,
        repo: IQuotationRepository,
        suppliers: ISupplierRepository,
        tenders: ITenderRepository,
    ):
        self.repo = repo
        self.suppliers = suppliers
        self.tenders = tenders

    async def _company(
        self, user_id: UUID, tender_id: UUID, supplier_id: UUID | None
    ) -> UUID:
        supplier = await resolver_empresa(self.suppliers, user_id, supplier_id)
        if supplier is None:
            raise QuotationCompanyRequired(
                "Registra tu empresa para generar una cotización."
            )
        if not await self.tenders.get_tenders(TenderFilters(ids=[tender_id])):
            raise TenderNotFound(tender_id)
        return supplier.id

    async def get(
        self, user_id: UUID, tender_id: UUID, supplier_id: UUID | None = None
    ) -> Quotation:
        supplier_id = await self._company(user_id, tender_id, supplier_id)
        quotation = await self.repo.get(supplier_id, tender_id)
        if quotation is None:
            raise QuotationNotFound("Todavía no hay una cotización guardada.")
        return quotation

    async def save(
        self,
        user_id: UUID,
        tender_id: UUID,
        data: QuotationInput,
        supplier_id: UUID | None = None,
    ) -> Quotation:
        supplier_id = await self._company(user_id, tender_id, supplier_id)
        return await self.repo.save(supplier_id, tender_id, data)
