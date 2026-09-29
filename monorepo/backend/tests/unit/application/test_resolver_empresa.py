"""Pruebas de `resolver_empresa`: la empresa activa manda sobre la propia (#260)."""

from uuid import uuid4

import pytest

from app.application.use_cases.supplier.resolver_empresa import resolver_empresa
from app.domain.entities.supplier import Supplier
from tests.unit.application.fakes import InMemorySupplierRepository


async def _dos_empresas():
    repo = InMemorySupplierRepository()
    user_id = uuid4()
    propia = await repo.save(
        Supplier(rut="76.086.428-5", legal_name="Propia SpA", user_id=user_id)
    )
    activa = await repo.save(
        Supplier(rut="77.654.321-7", legal_name="Activa Ltda", user_id=uuid4())
    )
    return repo, user_id, propia, activa


@pytest.mark.asyncio
async def test_usa_la_empresa_activa_si_viene():
    repo, user_id, _, activa = await _dos_empresas()

    assert await resolver_empresa(repo, user_id, activa.id) == activa


@pytest.mark.asyncio
async def test_sin_empresa_activa_usa_la_propia():
    repo, user_id, propia, _ = await _dos_empresas()

    assert await resolver_empresa(repo, user_id, None) == propia


@pytest.mark.asyncio
async def test_si_la_activa_no_existe_usa_la_propia():
    repo, user_id, propia, _ = await _dos_empresas()

    assert await resolver_empresa(repo, user_id, uuid4()) == propia


@pytest.mark.asyncio
async def test_sin_activa_ni_propia_devuelve_none():
    repo = InMemorySupplierRepository()

    assert await resolver_empresa(repo, uuid4(), None) is None
