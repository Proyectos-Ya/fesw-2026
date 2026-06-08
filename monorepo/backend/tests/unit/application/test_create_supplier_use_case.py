"""
Pruebas unitarias de CreateSupplierUseCase.

Verifican explícitamente que los datos se persisten en el repositorio SQL
(InMemorySupplierRepository) y en el repositorio vectorial que representa
Qdrant (FakeSupplierVectorRepository), y que los errores de negocio dejan
ambos stores intactos.
"""
import pytest

from app.application.schemas.supplier_schema import CreateSupplierSchema
from app.application.use_cases.supplier.create_supplier import CreateSupplierUseCase
from app.domain.errors.supplier_errors import (
    SupplierAlreadyExists,
    SupplierValidationError,
)
from tests.unit.application.fakes import (
    FakeSupplierVectorRepository,
    InMemorySupplierRepository,
)

VALID_RUT = "76086428-5"
OTHER_VALID_RUT = "77777777-7"
# Mismo cuerpo que VALID_RUT pero con dígito verificador incorrecto
INVALID_RUT = "76086428-0"
SUPPLIER_DATA = CreateSupplierSchema(rut=VALID_RUT, legal_name="Empresa SpA")


@pytest.fixture
def supplier_repo() -> InMemorySupplierRepository:
    return InMemorySupplierRepository()


@pytest.fixture
def vector_repo() -> FakeSupplierVectorRepository:
    return FakeSupplierVectorRepository()


@pytest.fixture
def use_case(
    supplier_repo: InMemorySupplierRepository,
    vector_repo: FakeSupplierVectorRepository,
) -> CreateSupplierUseCase:
    return CreateSupplierUseCase(supplier_repo, vector_repo)


# ---------------------------------------------------------------------------
# Persistencia en SQL
# ---------------------------------------------------------------------------


async def test_supplier_saved_in_sql_by_rut(use_case: CreateSupplierUseCase, supplier_repo: InMemorySupplierRepository) -> None:
    """El proveedor queda recuperable desde el repo SQL por RUT."""
    supplier = await use_case.execute(SUPPLIER_DATA)

    stored = await supplier_repo.get_by_rut(VALID_RUT)
    assert stored is not None
    assert stored.id == supplier.id


async def test_supplier_saved_in_sql_by_id(use_case: CreateSupplierUseCase, supplier_repo: InMemorySupplierRepository) -> None:
    """El proveedor queda recuperable desde el repo SQL por UUID."""
    supplier = await use_case.execute(SUPPLIER_DATA)

    stored = await supplier_repo.get_by_id(supplier.id)
    assert stored is not None
    assert stored.rut == VALID_RUT


# ---------------------------------------------------------------------------
# Persistencia en Qdrant (vector store)
# ---------------------------------------------------------------------------


async def test_supplier_indexed_in_qdrant(use_case: CreateSupplierUseCase, vector_repo: FakeSupplierVectorRepository) -> None:
    """El ID del proveedor se registra en el repositorio vectorial (Qdrant)."""
    supplier = await use_case.execute(SUPPLIER_DATA)

    assert supplier.id in vector_repo.upserts


async def test_qdrant_receives_exact_supplier_id(use_case: CreateSupplierUseCase, vector_repo: FakeSupplierVectorRepository) -> None:
    """El ID enviado a Qdrant coincide con el UUID persistido en SQL."""
    supplier = await use_case.execute(SUPPLIER_DATA)

    assert vector_repo.upserts[0] == supplier.id


async def test_qdrant_receives_one_upsert_per_creation(use_case: CreateSupplierUseCase, vector_repo: FakeSupplierVectorRepository) -> None:
    """Crear un proveedor genera exactamente un upsert en Qdrant, no más."""
    await use_case.execute(SUPPLIER_DATA)

    assert len(vector_repo.upserts) == 1


# ---------------------------------------------------------------------------
# Invariantes de integridad: errores de negocio no contaminan los stores
# ---------------------------------------------------------------------------


async def test_duplicate_rut_does_not_write_qdrant(
    supplier_repo: InMemorySupplierRepository,
    vector_repo: FakeSupplierVectorRepository,
) -> None:
    """Si el RUT ya existe, la operación falla antes de indexar en Qdrant."""
    use_case = CreateSupplierUseCase(supplier_repo, vector_repo)

    # Primera creación exitosa
    await use_case.execute(SUPPLIER_DATA)
    upserts_after_first = len(vector_repo.upserts)

    # Segundo intento con el mismo RUT
    with pytest.raises(SupplierAlreadyExists):
        await use_case.execute(SUPPLIER_DATA)

    assert len(vector_repo.upserts) == upserts_after_first


async def test_duplicate_rut_does_not_add_extra_sql_row(
    supplier_repo: InMemorySupplierRepository,
    vector_repo: FakeSupplierVectorRepository,
) -> None:
    """Si el RUT ya existe, el repo SQL queda con exactamente un proveedor."""
    use_case = CreateSupplierUseCase(supplier_repo, vector_repo)
    await use_case.execute(SUPPLIER_DATA)

    with pytest.raises(SupplierAlreadyExists):
        await use_case.execute(SUPPLIER_DATA)

    assert len(supplier_repo.suppliers) == 1


# ---------------------------------------------------------------------------
# RUT inválido: falla la validación antes de tocar SQL o Qdrant
# ---------------------------------------------------------------------------


async def test_invalid_rut_raises_validation_error(use_case: CreateSupplierUseCase) -> None:
    """Un RUT con dígito verificador incorrecto lanza SupplierValidationError."""
    data = CreateSupplierSchema(rut=INVALID_RUT, legal_name="Empresa SpA")

    with pytest.raises(SupplierValidationError):
        await use_case.execute(data)


async def test_invalid_rut_writes_neither_sql_nor_qdrant(
    supplier_repo: InMemorySupplierRepository,
    vector_repo: FakeSupplierVectorRepository,
) -> None:
    """Un RUT inválido falla en la validación: ni SQL ni Qdrant reciben datos."""
    use_case = CreateSupplierUseCase(supplier_repo, vector_repo)
    data = CreateSupplierSchema(rut=INVALID_RUT, legal_name="Empresa SpA")

    with pytest.raises(SupplierValidationError):
        await use_case.execute(data)

    assert len(supplier_repo.suppliers) == 0
    assert len(vector_repo.upserts) == 0
