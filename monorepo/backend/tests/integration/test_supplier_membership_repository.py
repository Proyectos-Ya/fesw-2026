from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.domain.entities.supplier_invitation import (
    InvitationStatus,
    SupplierInvitation,
)
from app.domain.entities.supplier_member import (
    MemberRole,
    MemberStatus,
    SupplierMember,
)
from app.infrastructure.repositories.sql_supplier_invitation_repository import (
    SqlSupplierInvitationRepository,
)
from app.infrastructure.repositories.sql_supplier_member_repository import (
    SqlSupplierMemberRepository,
)
from app.infrastructure.repositories.supplier_model import SupplierModel
from app.infrastructure.repositories.user_model import UserModel
from app.shared.datetime_utils import utc_now_naive


async def seed_user_and_supplier(session: AsyncSession):
    user_id = uuid4()
    user = UserModel(
        id=user_id,
        email=f"user_{user_id.hex[:8]}@demo.cl",
        hashed_password="hashed_password_123",
        full_name="Usuario Prueba",
        created_at=utc_now_naive(),
        updated_at=utc_now_naive(),
    )
    session.add(user)

    supplier_id = uuid4()
    supplier = SupplierModel(
        id=supplier_id,
        rut="76.123.456-7",
        legal_name="Empresa Alpha SpA",
        trade_name="Alpha Tech",
        created_at=utc_now_naive(),
        updated_at=utc_now_naive(),
    )
    session.add(supplier)
    await session.commit()
    return user_id, supplier_id


@pytest.mark.asyncio
async def test_supplier_member_crud(db_session: AsyncSession):
    user_id, supplier_id = await seed_user_and_supplier(db_session)
    repo = SqlSupplierMemberRepository(db_session)

    # 1. Save member
    member = SupplierMember(
        user_id=user_id,
        supplier_id=supplier_id,
        role=MemberRole.ADMIN,
        status=MemberStatus.ACTIVE,
    )
    saved = await repo.save(member)
    assert saved.id == member.id
    assert saved.role == MemberRole.ADMIN

    # 2. Get by ID
    fetched = await repo.get_by_id(member.id)
    assert fetched is not None
    assert fetched.user_id == user_id
    assert fetched.supplier_id == supplier_id

    # 3. Get by user and supplier
    by_pair = await repo.get_by_user_and_supplier(user_id, supplier_id)
    assert by_pair is not None
    assert by_pair.id == member.id

    # 4. List by user_id
    user_members = await repo.list_by_user_id(user_id)
    assert len(user_members) == 1
    assert user_members[0].role == MemberRole.ADMIN

    # 5. List user workspaces
    workspaces = await repo.list_user_workspaces(user_id)
    assert len(workspaces) == 1
    assert workspaces[0].supplier_id == supplier_id
    assert workspaces[0].legal_name == "Empresa Alpha SpA"
    assert workspaces[0].role == MemberRole.ADMIN

    # 6. Update role
    member.role = MemberRole.MEMBER
    updated = await repo.update(member)
    assert updated.role == MemberRole.MEMBER

    # 7. Delete
    deleted = await repo.delete(member.id)
    assert deleted is True
    assert await repo.get_by_id(member.id) is None


@pytest.mark.asyncio
async def test_supplier_invitation_crud(db_session: AsyncSession):
    user_id, supplier_id = await seed_user_and_supplier(db_session)
    repo = SqlSupplierInvitationRepository(db_session)

    invitation = SupplierInvitation(
        supplier_id=supplier_id,
        email="socio@alpha.cl",
        role=MemberRole.MEMBER,
        invited_by_user_id=user_id,
        token="token_unico_invitacion_123",
        status=InvitationStatus.PENDING,
        expires_at=utc_now_naive() + timedelta(days=7),
    )


    # 1. Save
    saved = await repo.save(invitation)
    assert saved.id == invitation.id

    # 2. Get by token
    by_token = await repo.get_by_token("token_unico_invitacion_123")
    assert by_token is not None
    assert by_token.email == "socio@alpha.cl"
    assert by_token.role == MemberRole.MEMBER

    # 3. List by email
    by_email = await repo.list_by_email("socio@alpha.cl")
    assert len(by_email) == 1

    # 4. List by supplier
    by_sup = await repo.list_by_supplier_id(supplier_id)
    assert len(by_sup) == 1


    # 5. Update status
    invitation.status = InvitationStatus.ACCEPTED
    invitation.accepted_at = utc_now_naive()
    updated = await repo.update(invitation)
    assert updated.status == InvitationStatus.ACCEPTED
    assert updated.accepted_at is not None


# ---------------------------------------------------------------------------
# El esquema de membresías tiene que ser el que creó la migración (PENDIENTES
# 3.29). Esta base se arma desde los modelos, así que estos tests fallan si un
# modelo deja de declarar lo que la migración `f1e2d3c4b5a6` aplicó.
# ---------------------------------------------------------------------------


async def _membresia_e_invitacion(session: AsyncSession):
    user_id, supplier_id = await seed_user_and_supplier(session)
    await SqlSupplierMemberRepository(session).save(
        SupplierMember(
            user_id=user_id,
            supplier_id=supplier_id,
            role=MemberRole.ADMIN,
            status=MemberStatus.ACTIVE,
        )
    )
    await SqlSupplierInvitationRepository(session).save(
        SupplierInvitation(
            supplier_id=supplier_id,
            email="socio@alpha.cl",
            role=MemberRole.MEMBER,
            invited_by_user_id=user_id,
            token=f"token_{uuid4().hex}",
            status=InvitationStatus.PENDING,
            expires_at=utc_now_naive() + timedelta(days=7),
        )
    )
    return user_id, supplier_id


async def _contar(session: AsyncSession, tabla: str, columna: str, valor) -> int:
    resultado = await session.execute(
        text(f"SELECT count(*) FROM {tabla} WHERE {columna} = :v"), {"v": valor}
    )
    return int(resultado.scalar_one())


@pytest.mark.asyncio
async def test_borrar_una_empresa_arrastra_sus_membresias_e_invitaciones(
    db_session: AsyncSession,
):
    _, supplier_id = await _membresia_e_invitacion(db_session)

    await db_session.execute(text("DELETE FROM supplier WHERE id = :id"), {"id": supplier_id})
    await db_session.commit()

    assert await _contar(db_session, "supplier_members", "supplier_id", supplier_id) == 0
    assert await _contar(db_session, "supplier_invitations", "supplier_id", supplier_id) == 0


@pytest.mark.asyncio
async def test_borrar_un_usuario_arrastra_sus_membresias_e_invitaciones_enviadas(
    db_session: AsyncSession,
):
    user_id, supplier_id = await _membresia_e_invitacion(db_session)
    # La empresa no cuelga del usuario en este caso: se la desvincula para que el
    # borrado solo pase por las tablas de membresías.
    await db_session.execute(
        text("UPDATE supplier SET user_id = NULL WHERE id = :id"), {"id": supplier_id}
    )

    await db_session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
    await db_session.commit()

    assert await _contar(db_session, "supplier_members", "user_id", user_id) == 0
    assert (
        await _contar(db_session, "supplier_invitations", "invited_by_user_id", user_id)
        == 0
    )


@pytest.mark.asyncio
async def test_la_base_pone_rol_y_estado_por_defecto(db_session: AsyncSession):
    user_id, supplier_id = await seed_user_and_supplier(db_session)

    await db_session.execute(
        text(
            "INSERT INTO supplier_members (id, user_id, supplier_id, created_at, updated_at)"
            " VALUES (:id, :u, :s, now(), now())"
        ),
        {"id": uuid4(), "u": user_id, "s": supplier_id},
    )
    await db_session.commit()

    fila = (
        await db_session.execute(
            text("SELECT role, status FROM supplier_members WHERE user_id = :u"),
            {"u": user_id},
        )
    ).one()
    assert (fila.role, fila.status) == ("member", "active")

