from datetime import timedelta
from uuid import uuid4

import pytest

from app.application.schemas.workspace_schema import SwitchWorkspaceSchema
from app.application.use_cases.workspace.accept_supplier_invitation import (
    AcceptSupplierInvitationUseCase,
)
from app.application.use_cases.workspace.revoke_supplier_member import (
    RevokeSupplierMemberUseCase,
)
from app.application.use_cases.workspace.switch_workspace import (
    SwitchWorkspaceUseCase,
)
from app.domain.entities.supplier import Supplier
from app.domain.entities.supplier_invitation import (
    InvitationStatus,
    SupplierInvitation,
)
from app.domain.entities.supplier_member import (
    MemberRole,
    MemberStatus,
    SupplierMember,
)
from app.domain.entities.user import User
from app.domain.errors.membership_errors import (
    CannotRevokeOwnMembership,
    MembershipNotFound,
    UnauthorizedWorkspaceAction,
)
from app.shared.datetime_utils import utc_now_naive
from tests.unit.application.fakes import (
    InMemorySupplierInvitationRepository,
    InMemorySupplierMemberRepository,
    InMemorySupplierRepository,
    InMemoryUserRepository,
)


@pytest.fixture
def repos():
    users = InMemoryUserRepository()
    suppliers = InMemorySupplierRepository()
    members = InMemorySupplierMemberRepository(supplier_repo=suppliers)
    invitations = InMemorySupplierInvitationRepository()
    return users, suppliers, members, invitations


@pytest.mark.asyncio
async def test_ca1_accept_and_switch_workspace_record_last_access_at(repos):
    users, suppliers, members, invitations = repos
    admin = await users.save(
        User(id=uuid4(), email="admin@empresa.cl", full_name="Admin")
    )
    rep = await users.save(
        User(id=uuid4(), email="rep@empresa.cl", full_name="Representante")
    )
    supplier = await suppliers.save(
        Supplier(
            id=uuid4(),
            user_id=admin.id,
            rut="76.123.456-0",
            legal_name="Empresa Demo SpA",
        )
    )
    invitation = await invitations.save(
        SupplierInvitation(
            supplier_id=supplier.id,
            email=rep.email,
            role=MemberRole.MEMBER,
            invited_by_user_id=admin.id,
            token="tok-hu13-1",
            status=InvitationStatus.PENDING,
            expires_at=utc_now_naive() + timedelta(days=7),
        )
    )

    accept_uc = AcceptSupplierInvitationUseCase(
        invitation_repo=invitations,
        member_repo=members,
    )
    created_member = await accept_uc.execute(token=invitation.token, current_user=rep)
    assert created_member.last_access_at is not None

    # Simular un acceso antiguo (> 10 minutos atrás) y verificar que SwitchWorkspaceUseCase lo actualiza
    old_access = utc_now_naive() - timedelta(minutes=10)
    created_member.last_access_at = old_access
    await members.update(created_member)

    switch_uc = SwitchWorkspaceUseCase(member_repo=members, supplier_repo=suppliers)
    await switch_uc.execute(
        current_user=rep,
        data=SwitchWorkspaceSchema(supplier_id=supplier.id),
    )

    updated_member = await members.get_by_id(created_member.id)
    assert updated_member is not None
    assert updated_member.last_access_at is not None
    assert updated_member.last_access_at > old_access


@pytest.mark.asyncio
async def test_ca2_admin_can_revoke_member_access(repos):
    users, suppliers, members, _ = repos
    admin = await users.save(
        User(id=uuid4(), email="admin@empresa.cl", full_name="Admin")
    )
    rep = await users.save(
        User(id=uuid4(), email="rep@empresa.cl", full_name="Representante")
    )
    supplier = await suppliers.save(
        Supplier(
            id=uuid4(),
            user_id=admin.id,
            rut="76.123.456-0",
            legal_name="Empresa Demo SpA",
        )
    )
    await members.save(
        SupplierMember(
            user_id=admin.id,
            supplier_id=supplier.id,
            role=MemberRole.ADMIN,
            status=MemberStatus.ACTIVE,
        )
    )
    rep_member = await members.save(
        SupplierMember(
            user_id=rep.id,
            supplier_id=supplier.id,
            role=MemberRole.MEMBER,
            status=MemberStatus.ACTIVE,
        )
    )

    revoke_uc = RevokeSupplierMemberUseCase(
        member_repo=members,
        supplier_repo=suppliers,
    )
    revoked = await revoke_uc.execute(
        supplier_id=supplier.id,
        member_id=rep_member.id,
        actor_user_id=admin.id,
    )

    assert revoked.id == rep_member.id
    assert revoked.status == MemberStatus.INACTIVE

    stored = await members.get_by_id(rep_member.id)
    assert stored is not None
    assert stored.status == MemberStatus.INACTIVE


@pytest.mark.asyncio
async def test_ca4_admin_cannot_revoke_own_membership(repos):
    users, suppliers, members, _ = repos
    admin = await users.save(
        User(id=uuid4(), email="admin@empresa.cl", full_name="Admin")
    )
    supplier = await suppliers.save(
        Supplier(
            id=uuid4(),
            user_id=admin.id,
            rut="76.123.456-0",
            legal_name="Empresa Demo SpA",
        )
    )
    admin_member = await members.save(
        SupplierMember(
            user_id=admin.id,
            supplier_id=supplier.id,
            role=MemberRole.ADMIN,
            status=MemberStatus.ACTIVE,
        )
    )

    revoke_uc = RevokeSupplierMemberUseCase(
        member_repo=members,
        supplier_repo=suppliers,
    )
    with pytest.raises(CannotRevokeOwnMembership):
        await revoke_uc.execute(
            supplier_id=supplier.id,
            member_id=admin_member.id,
            actor_user_id=admin.id,
        )


@pytest.mark.asyncio
async def test_ca5_non_admin_cannot_revoke_member_access(repos):
    users, suppliers, members, _ = repos
    admin = await users.save(
        User(id=uuid4(), email="admin@empresa.cl", full_name="Admin")
    )
    rep1 = await users.save(
        User(id=uuid4(), email="rep1@empresa.cl", full_name="Representante 1")
    )
    rep2 = await users.save(
        User(id=uuid4(), email="rep2@empresa.cl", full_name="Representante 2")
    )
    supplier = await suppliers.save(
        Supplier(
            id=uuid4(),
            user_id=admin.id,
            rut="76.123.456-0",
            legal_name="Empresa Demo SpA",
        )
    )
    await members.save(
        SupplierMember(
            user_id=rep1.id,
            supplier_id=supplier.id,
            role=MemberRole.MEMBER,
            status=MemberStatus.ACTIVE,
        )
    )
    rep2_member = await members.save(
        SupplierMember(
            user_id=rep2.id,
            supplier_id=supplier.id,
            role=MemberRole.MEMBER,
            status=MemberStatus.ACTIVE,
        )
    )

    revoke_uc = RevokeSupplierMemberUseCase(
        member_repo=members,
        supplier_repo=suppliers,
    )
    with pytest.raises(UnauthorizedWorkspaceAction):
        await revoke_uc.execute(
            supplier_id=supplier.id,
            member_id=rep2_member.id,
            actor_user_id=rep1.id,
        )


@pytest.mark.asyncio
async def test_revoke_nonexistent_or_other_supplier_member_raises_not_found(repos):
    users, suppliers, members, _ = repos
    admin = await users.save(
        User(id=uuid4(), email="admin@empresa.cl", full_name="Admin")
    )
    supplier = await suppliers.save(
        Supplier(
            id=uuid4(),
            user_id=admin.id,
            rut="76.123.456-0",
            legal_name="Empresa Demo SpA",
        )
    )
    await members.save(
        SupplierMember(
            user_id=admin.id,
            supplier_id=supplier.id,
            role=MemberRole.ADMIN,
            status=MemberStatus.ACTIVE,
        )
    )

    revoke_uc = RevokeSupplierMemberUseCase(
        member_repo=members,
        supplier_repo=suppliers,
    )
    with pytest.raises(MembershipNotFound):
        await revoke_uc.execute(
            supplier_id=supplier.id,
            member_id=uuid4(),
            actor_user_id=admin.id,
        )
