from uuid import UUID

from app.application.repositories.supplier_repository import ISupplierRepository
from app.domain.entities.supplier import Supplier
from app.domain.errors.supplier_errors import SupplierNotFoundForUser


class GetSupplierByUserUseCase:
    """Recupera la empresa asociada a un usuario (su perfil de proveedor)."""

    def __init__(self, repo: ISupplierRepository):
        self.repo = repo

    async def execute(self, user_id: UUID) -> Supplier:
        supplier = await self.repo.get_by_user_id(user_id)
        if supplier is None:
            raise SupplierNotFoundForUser(user_id)
        return supplier
