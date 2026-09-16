"""SupplierRepository contra Postgres real: unicidad y unidad de trabajo.

El índice del RUT normalizado lo crea `create_all` desde el modelo, que lo
declara con la misma expresión que la migración `d7f2a9c41b58`.
"""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domain.entities.supplier import Supplier
from app.domain.errors.supplier_errors import (
    SupplierAlreadyExists,
    UserAlreadyHasSupplier,
)
from app.infrastructure.repositories.supplier_repository import SupplierRepository
from app.infrastructure.repositories.user_model import UserModel
from app.shared.datetime_utils import utc_now_naive

RUT = "76.086.428-5"
OTHER_RUT = "77.777.777-7"


async def _create_user(session: AsyncSession) -> UUID:
    now = utc_now_naive()
    # El id se toma antes del commit: después la sesión expira el objeto, y leer
    # un atributo dispara una recarga síncrona que falla con MissingGreenlet.
    user_id = uuid4()
    user = UserModel(
        id=user_id,
        email=f"{uuid4()}@example.com",
        full_name="Dueño Empresa",
        created_at=now,
        updated_at=now,
    )
    session.add(user)
    await session.commit()
    return user_id


async def test_legacy_rut_in_other_format_raises_supplier_already_exists(
    db_session: AsyncSession,
) -> None:
    """Una fila anterior a la normalización choca con el mismo RUT formateado."""
    now = utc_now_naive()
    await db_session.exec(  # type: ignore[call-overload]
        text(
            "INSERT INTO supplier (id, rut, legal_name, created_at, updated_at) "
            "VALUES (:id, '76086428-5', 'Legado SpA', :now, :now)"
        ).bindparams(id=uuid4(), now=now)
    )
    await db_session.commit()
    repo = SupplierRepository(db_session)

    with pytest.raises(SupplierAlreadyExists):
        await repo.add(Supplier(rut=RUT, legal_name="Empresa SpA"))


async def test_repeated_user_id_raises_user_already_has_supplier(
    db_session: AsyncSession,
) -> None:
    """Un segundo proveedor para el mismo usuario es un conflicto de dominio."""
    user_id = await _create_user(db_session)
    repo = SupplierRepository(db_session)
    await repo.save(Supplier(rut=RUT, legal_name="Empresa SpA", user_id=user_id))

    with pytest.raises(UserAlreadyHasSupplier):
        await repo.add(
            Supplier(rut=OTHER_RUT, legal_name="Otra Empresa SpA", user_id=user_id)
        )


async def test_session_is_usable_after_a_conflict(db_session: AsyncSession) -> None:
    """Tras el rollback interno se puede seguir escribiendo con la misma sesión."""
    repo = SupplierRepository(db_session)
    await repo.save(Supplier(rut=RUT, legal_name="Empresa SpA"))

    with pytest.raises(SupplierAlreadyExists):
        await repo.add(Supplier(rut=RUT, legal_name="Duplicada SpA"))

    await repo.save(Supplier(rut=OTHER_RUT, legal_name="Otra Empresa SpA"))
    assert await repo.get_by_rut(OTHER_RUT) is not None


async def test_add_and_rollback_leaves_no_row(
    db_session: AsyncSession, integration_engine: AsyncEngine
) -> None:
    """`add` sin `commit` no deja nada después de `rollback`."""
    repo = SupplierRepository(db_session)
    await repo.add(Supplier(rut=RUT, legal_name="Empresa SpA"))
    await repo.rollback()

    async with AsyncSession(integration_engine) as other_session:
        assert await SupplierRepository(other_session).get_by_rut(RUT) is None


async def test_row_is_invisible_to_other_sessions_until_commit(
    db_session: AsyncSession, integration_engine: AsyncEngine
) -> None:
    """Lo pendiente no se ve desde otra conexión hasta confirmar."""
    repo = SupplierRepository(db_session)
    await repo.add(Supplier(rut=RUT, legal_name="Empresa SpA"))

    async with AsyncSession(integration_engine) as other_session:
        assert await SupplierRepository(other_session).get_by_rut(RUT) is None

    await repo.commit()

    async with AsyncSession(integration_engine) as other_session:
        assert await SupplierRepository(other_session).get_by_rut(RUT) is not None
