from uuid import UUID

from app.application.repositories.supplier_repository import ISupplierRepository
from app.domain.entities.supplier import Supplier
from app.domain.errors.supplier_errors import SupplierNotFound


class GetSupplierUseCase:

    def __init__(self, repo: ISupplierRepository):
        self.repo = repo

    async def execute(self, supplier_id: UUID) -> Supplier:
        supplier = await self.repo.get_by_id(supplier_id)
        if not supplier:
            raise SupplierNotFound(str(supplier_id))
        return supplier
