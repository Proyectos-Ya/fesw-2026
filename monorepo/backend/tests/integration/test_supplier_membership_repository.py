from datetime import timedelta
from uuid import uuid4
import pytest
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
