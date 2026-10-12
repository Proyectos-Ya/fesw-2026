from uuid import UUID

from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.use_cases.supplier.resolver_empresa import resolver_empresa
from app.domain.entities.supplier import Supplier
from app.domain.errors.supplier_errors import SupplierNotFoundForUser


async def empresa_o_error(
    repo: ISupplierRepository, user_id: UUID, supplier_id: UUID | None
) -> Supplier:
    """La empresa activa del usuario, o la propia; sin ninguna no hay a quién escribirle."""
    supplier = await resolver_empresa(repo, user_id, supplier_id)
    if supplier is None:
        raise SupplierNotFoundForUser(user_id)
    return supplier
