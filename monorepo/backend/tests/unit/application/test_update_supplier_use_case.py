"""
Pruebas unitarias de UpdateSupplierUseCase.

Verifican la actualización parcial de la empresa del usuario, el re-indexado
en Qdrant solo cuando cambian campos de matching, y el error cuando el
usuario no tiene empresa.
"""

from uuid import uuid4

import pytest

from app.application.schemas.supplier_schema import UpdateSupplierSchema
from app.application.use_cases.supplier.update_supplier import UpdateSupplierUseCase
from app.domain.entities.supplier import Supplier
from app.domain.errors.supplier_errors import SupplierNotFoundForUser
from tests.unit.application.fakes import (
    FakeEmbeddingService,
    FakeSupplierVectorRepository,
    InMemorySupplierRepository,
)

VALID_RUT = "76086428-5"


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
) -> UpdateSupplierUseCase:
    return UpdateSupplierUseCase(supplier_repo, vector_repo, FakeEmbeddingService())


async def _seed_supplier(repo: InMemorySupplierRepository, owner_id) -> Supplier:
    supplier = Supplier(
        rut=VALID_RUT,
        legal_name="Empresa SpA",
        description="Obras civiles",
        num_employees=10,
        user_id=owner_id,
    )
    return await repo.save(supplier)


async def test_updates_only_sent_fields(
    use_case: UpdateSupplierUseCase, supplier_repo: InMemorySupplierRepository
) -> None:
    """Los campos enviados se actualizan y el resto se conserva intacto."""
    owner_id = uuid4()
    await _seed_supplier(supplier_repo, owner_id)

    updated = await use_case.execute(
        owner_id, UpdateSupplierSchema(legal_name="Empresa Renovada SpA")
    )

    assert updated.legal_name == "Empresa Renovada SpA"
    assert updated.description == "Obras civiles"
    assert updated.rut == VALID_RUT


async def test_raises_when_user_has_no_supplier(
    use_case: UpdateSupplierUseCase,
) -> None:
    """Editar sin tener empresa lanza SupplierNotFoundForUser."""
    with pytest.raises(SupplierNotFoundForUser):
        await use_case.execute(uuid4(), UpdateSupplierSchema(legal_name="X SpA"))


async def test_matching_field_change_reindexes_vector(
    use_case: UpdateSupplierUseCase,
    supplier_repo: InMemorySupplierRepository,
    vector_repo: FakeSupplierVectorRepository,
) -> None:
    """Cambiar la descripción (campo de matching) re-indexa en Qdrant."""
    owner_id = uuid4()
    seeded = await _seed_supplier(supplier_repo, owner_id)

    updated = await use_case.execute(
        owner_id, UpdateSupplierSchema(description="Montaje industrial")
    )

    assert vector_repo.upserts == [seeded.id]
    assert updated.profile_changed_at is not None


async def test_trade_name_change_reindexes_vector(
    use_case: UpdateSupplierUseCase,
    supplier_repo: InMemorySupplierRepository,
    vector_repo: FakeSupplierVectorRepository,
) -> None:
    """Cambiar el nombre de fantasía (campo de matching) re-indexa en Qdrant."""
    owner_id = uuid4()
    seeded = await _seed_supplier(supplier_repo, owner_id)

    updated = await use_case.execute(
        owner_id, UpdateSupplierSchema(trade_name="La Constructora")
    )

    assert updated.trade_name == "La Constructora"
    assert vector_repo.upserts == [seeded.id]


async def test_non_matching_field_change_does_not_reindex(
    use_case: UpdateSupplierUseCase,
    supplier_repo: InMemorySupplierRepository,
    vector_repo: FakeSupplierVectorRepository,
) -> None:
    """Cambiar solo num_employees no toca Qdrant ni profile_changed_at."""
    owner_id = uuid4()
    await _seed_supplier(supplier_repo, owner_id)

    updated = await use_case.execute(owner_id, UpdateSupplierSchema(num_employees=25))

    assert updated.num_employees == 25
    assert vector_repo.upserts == []
    assert updated.profile_changed_at is None


async def test_sending_same_values_is_a_noop(
    use_case: UpdateSupplierUseCase,
    supplier_repo: InMemorySupplierRepository,
    vector_repo: FakeSupplierVectorRepository,
) -> None:
    """Enviar los mismos valores actuales no re-indexa ni cambia updated_at."""
    owner_id = uuid4()
    seeded = await _seed_supplier(supplier_repo, owner_id)

    updated = await use_case.execute(
        owner_id, UpdateSupplierSchema(legal_name="Empresa SpA")
    )

    assert updated.updated_at == seeded.updated_at
    assert vector_repo.upserts == []


# ---------------------------------------------------------------------------
# El proveedor externo de embeddings se cae
#
# Mismo defecto que en la creación: el perfil se guardaba antes de recalcular
# el vector, así que un timeout dejaba el texto nuevo en SQL apuntando a un
# vector viejo. El matching seguía usando el perfil anterior sin que nada lo
# indicara. Si el embedding falla, la edición completa no se aplica.
# ---------------------------------------------------------------------------


class BrokenEmbeddingService(FakeEmbeddingService):
    """Simula el proveedor de embeddings caído o pasado de timeout."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise TimeoutError("El servicio de embeddings no respondió a tiempo")


async def test_embedding_failure_does_not_persist_matching_change(
    supplier_repo: InMemorySupplierRepository,
    vector_repo: FakeSupplierVectorRepository,
) -> None:
    """Si el embedding falla, el perfil no queda desincronizado del vector."""
    owner_id = uuid4()
    await _seed_supplier(supplier_repo, owner_id)
    use_case = UpdateSupplierUseCase(
        supplier_repo, vector_repo, BrokenEmbeddingService()
    )

    with pytest.raises(TimeoutError):
        await use_case.execute(
            owner_id, UpdateSupplierSchema(description="Montaje industrial")
        )

    stored = await supplier_repo.get_by_user_id(owner_id)
    assert stored is not None
    assert stored.description == "Obras civiles"
    assert len(vector_repo.upserts) == 0


async def test_embedding_failure_does_not_block_non_matching_change(
    supplier_repo: InMemorySupplierRepository,
    vector_repo: FakeSupplierVectorRepository,
) -> None:
    """Editar un campo que no alimenta el matching no llama al embedding.

    `num_employees` no entra en el texto que se vectoriza, así que la edición
    tiene que funcionar aunque el proveedor de embeddings esté caído.
    """
    owner_id = uuid4()
    await _seed_supplier(supplier_repo, owner_id)
    use_case = UpdateSupplierUseCase(
        supplier_repo, vector_repo, BrokenEmbeddingService()
    )

    updated = await use_case.execute(owner_id, UpdateSupplierSchema(num_employees=25))

    assert updated.num_employees == 25
    assert len(vector_repo.upserts) == 0
