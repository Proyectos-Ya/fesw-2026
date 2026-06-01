from app.application.repositories.supplier_repository import ISupplierRepository
from app.domain.entities.supplier import Supplier
from app.domain.errors.supplier_errors import SupplierNotFound


class GetSupplierUseCase:

    def __init__(self, repo: ISupplierRepository):
        self.repo = repo

    async def execute(self, rut: str) -> Supplier:
        supplier = await self.repo.get_by_rut(rut)
        if not supplier:
            raise SupplierNotFound(rut)
        return supplier