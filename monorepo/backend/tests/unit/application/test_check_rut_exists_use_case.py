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


@pytest.mark.parametrize("consulted", ["76.086.428-5", "76086428-5", "760864285"])
async def test_detects_rut_regardless_of_format(
    supplier_repo: InMemorySupplierRepository, consulted: str
) -> None:
    """El RUT se encuentra aunque se consulte con otro formato que el guardado."""
    supplier = Supplier(rut="76.086.428-5", legal_name="Empresa SpA", user_id=uuid4())
    await supplier_repo.save(supplier)

    result = await CheckRutExistsUseCase(supplier_repo).execute(consulted)

    assert result is True


async def test_returns_false_for_invalid_rut(
    supplier_repo: InMemorySupplierRepository,
) -> None:
    """Un RUT inválido no puede estar registrado: devuelve False sin fallar."""
    result = await CheckRutExistsUseCase(supplier_repo).execute("no-es-un-rut")

    assert result is False
