from uuid import UUID

from app.application.repositories.supplier_repository import ISupplierRepository
from app.domain.entities.supplier import Supplier


async def resolver_empresa(
    repo: ISupplierRepository, user_id: UUID, supplier_id: UUID | None
) -> Supplier | None:
    """Empresa con la que opera el usuario: la activa si viene y existe; si no, la propia.

    `supplier_id` sale del `WorkspaceContext`, que ya comprobó la membresía; nunca
    del cliente. Sin él se usa la empresa de la que el usuario es dueño, que es
    lo único que había antes de las empresas múltiples (HdU 14).
    """
    if supplier_id is not None:
        supplier = await repo.get_by_id(supplier_id)
        if supplier is not None:
            return supplier
    return await repo.get_by_user_id(user_id)
