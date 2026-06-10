"""
Pruebas unitarias de CheckRutExistsUseCase.

Verifica que el caso de uso informe si ya existe una empresa
registrada con el RUT consultado.
"""
from uuid import uuid4

import pytest

from app.application.use_cases.supplier.check_rut_exists import CheckRutExistsUseCase
from app.domain.entities.supplier import Supplier
from tests.unit.application.fakes import InMemorySupplierRepository

VALID_RUT = "76086428-5"


@pytest.fixture
def supplier_repo() -> InMemorySupplierRepository:
    return InMemorySupplierRepository()


async def test_returns_true_when_rut_already_registered(
    supplier_repo: InMemorySupplierRepository,
) -> None:
    """Devuelve True si ya hay una empresa con ese RUT."""
    supplier = Supplier(rut=VALID_RUT, legal_name="Empresa SpA", user_id=uuid4())
    await supplier_repo.save(supplier)

    result = await CheckRutExistsUseCase(supplier_repo).execute(VALID_RUT)

    assert result is True


async def test_returns_false_when_rut_not_registered(
    supplier_repo: InMemorySupplierRepository,
) -> None:
    """Devuelve False si ninguna empresa tiene ese RUT."""
    result = await CheckRutExistsUseCase(supplier_repo).execute(VALID_RUT)

    assert result is False
