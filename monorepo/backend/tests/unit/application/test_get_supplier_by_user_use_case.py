"""
Pruebas unitarias de GetSupplierByUserUseCase.

Verifica que el caso de uso recupere la empresa del usuario autenticado
y que falle con SupplierNotFoundForUser cuando el usuario no tiene empresa.
"""
from uuid import uuid4

import pytest

from app.application.use_cases.supplier.get_supplier_by_user import (
    GetSupplierByUserUseCase,
)
from app.domain.entities.supplier import Supplier
from app.domain.errors.supplier_errors import SupplierNotFoundForUser
from tests.unit.application.fakes import InMemorySupplierRepository

VALID_RUT = "76086428-5"


@pytest.fixture
def supplier_repo() -> InMemorySupplierRepository:
    return InMemorySupplierRepository()


async def test_returns_supplier_owned_by_user(
    supplier_repo: InMemorySupplierRepository,
) -> None:
    """Devuelve la empresa cuyo user_id coincide con el usuario consultado."""
    owner_id = uuid4()
    supplier = Supplier(rut=VALID_RUT, legal_name="Empresa SpA", user_id=owner_id)
    await supplier_repo.save(supplier)

    result = await GetSupplierByUserUseCase(supplier_repo).execute(owner_id)

    assert result.id == supplier.id
    assert result.user_id == owner_id


async def test_raises_when_user_has_no_supplier(
    supplier_repo: InMemorySupplierRepository,
) -> None:
    """Si el usuario no tiene empresa asociada lanza SupplierNotFoundForUser."""
    with pytest.raises(SupplierNotFoundForUser):
        await GetSupplierByUserUseCase(supplier_repo).execute(uuid4())
