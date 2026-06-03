from uuid import uuid4

import pytest

from app.application.schemas.supplier_schema import CreateSupplierSchema
from app.application.use_cases.membership.approve_join import ApproveJoinUseCase
from app.application.use_cases.membership.get_user_membership import (
    GetUserMembershipUseCase,
)
from app.application.use_cases.membership.list_memberships import ListMembershipsUseCase
from app.application.use_cases.membership.reject_join import RejectJoinUseCase
from app.application.use_cases.membership.request_join import RequestJoinUseCase
from app.application.use_cases.supplier.create_supplier import CreateSupplierUseCase
from app.domain.entities.membership import MembershipRole, MembershipStatus
from app.domain.errors.membership_errors import (
    AlreadyHasSupplier,
    MembershipNotFound,
    NotAuthorized,
)
from app.domain.errors.supplier_errors import SupplierNotFound
from tests.unit.application.fakes import (
    FakeSupplierVectorRepository,
    InMemoryMembershipRepository,
    InMemorySupplierRepository,
)

# RUT chileno válido para las pruebas
VALID_RUT = "76086428-5"


@pytest.fixture
def supplier_repo() -> InMemorySupplierRepository:
    return InMemorySupplierRepository()


@pytest.fixture
def vector_repo() -> FakeSupplierVectorRepository:
    return FakeSupplierVectorRepository()


@pytest.fixture
def membership_repo() -> InMemoryMembershipRepository:
    return InMemoryMembershipRepository()


async def _create_supplier(supplier_repo, vector_repo, membership_repo, admin_id, rut=VALID_RUT):
    data = CreateSupplierSchema(rut=rut, legal_name="Empresa SpA")
    return await CreateSupplierUseCase(supplier_repo, vector_repo, membership_repo).execute(
        data, admin_id
    )


async def test_create_supplier_makes_creator_admin(supplier_repo, vector_repo, membership_repo):
    admin_id = uuid4()
    supplier, membership = await _create_supplier(
        supplier_repo, vector_repo, membership_repo, admin_id
    )

    assert supplier.rut == VALID_RUT
    assert membership.user_id == admin_id
    assert membership.supplier_id == supplier.id
    assert membership.role == MembershipRole.ADMIN
    assert membership.status == MembershipStatus.ACTIVE
    assert membership.joined_at is not None


async def test_create_supplier_when_already_member_raises(
    supplier_repo, vector_repo, membership_repo
):
    admin_id = uuid4()
    await _create_supplier(supplier_repo, vector_repo, membership_repo, admin_id)

    with pytest.raises(AlreadyHasSupplier):
        await _create_supplier(
            supplier_repo, vector_repo, membership_repo, admin_id, rut="77777777-7"
        )


async def test_request_join_creates_pending(supplier_repo, vector_repo, membership_repo):
    admin_id = uuid4()
    supplier, _ = await _create_supplier(supplier_repo, vector_repo, membership_repo, admin_id)

    joiner_id = uuid4()
    membership = await RequestJoinUseCase(supplier_repo, membership_repo).execute(
        VALID_RUT, joiner_id
    )
    assert membership.status == MembershipStatus.PENDING
    assert membership.role == MembershipRole.MEMBER
    assert membership.supplier_id == supplier.id


async def test_request_join_unknown_rut_raises(supplier_repo, membership_repo):
    with pytest.raises(SupplierNotFound):
        await RequestJoinUseCase(supplier_repo, membership_repo).execute(
            VALID_RUT, uuid4()
        )


async def test_request_join_when_already_has_supplier_raises(
    supplier_repo, vector_repo, membership_repo
):
    admin_id = uuid4()
    await _create_supplier(supplier_repo, vector_repo, membership_repo, admin_id)
    with pytest.raises(AlreadyHasSupplier):
        await RequestJoinUseCase(supplier_repo, membership_repo).execute(
            VALID_RUT, admin_id
        )


async def test_approve_join_by_admin(supplier_repo, vector_repo, membership_repo):
    admin_id = uuid4()
    supplier, _ = await _create_supplier(supplier_repo, vector_repo, membership_repo, admin_id)
    joiner_id = uuid4()
    pending = await RequestJoinUseCase(supplier_repo, membership_repo).execute(
        VALID_RUT, joiner_id
    )

    approved = await ApproveJoinUseCase(membership_repo).execute(
        supplier.id, pending.id, admin_id
    )
    assert approved.status == MembershipStatus.ACTIVE
    assert approved.joined_at is not None


async def test_approve_join_by_non_admin_raises(supplier_repo, vector_repo, membership_repo):
    admin_id = uuid4()
    supplier, _ = await _create_supplier(supplier_repo, vector_repo, membership_repo, admin_id)
    joiner_id = uuid4()
    pending = await RequestJoinUseCase(supplier_repo, membership_repo).execute(
        VALID_RUT, joiner_id
    )

    # El propio solicitante (rol member, status pending) no puede auto-aprobarse
    with pytest.raises(NotAuthorized):
        await ApproveJoinUseCase(membership_repo).execute(
            supplier.id, pending.id, joiner_id
        )


async def test_approve_unknown_membership_raises(supplier_repo, vector_repo, membership_repo):
    admin_id = uuid4()
    supplier, _ = await _create_supplier(supplier_repo, vector_repo, membership_repo, admin_id)
    with pytest.raises(MembershipNotFound):
        await ApproveJoinUseCase(membership_repo).execute(supplier.id, uuid4(), admin_id)


async def test_reject_join_removes_request(supplier_repo, vector_repo, membership_repo):
    admin_id = uuid4()
    supplier, _ = await _create_supplier(supplier_repo, vector_repo, membership_repo, admin_id)
    joiner_id = uuid4()
    pending = await RequestJoinUseCase(supplier_repo, membership_repo).execute(
        VALID_RUT, joiner_id
    )

    await RejectJoinUseCase(membership_repo).execute(supplier.id, pending.id, admin_id)
    assert await membership_repo.get_by_id(pending.id) is None
    # Tras el rechazo el usuario puede volver a solicitar
    assert await membership_repo.get_by_user(joiner_id) is None


async def test_list_pending_for_admin(supplier_repo, vector_repo, membership_repo):
    admin_id = uuid4()
    supplier, _ = await _create_supplier(supplier_repo, vector_repo, membership_repo, admin_id)
    await RequestJoinUseCase(supplier_repo, membership_repo).execute(VALID_RUT, uuid4())

    pending = await ListMembershipsUseCase(membership_repo).execute(
        supplier.id, admin_id, MembershipStatus.PENDING
    )
    assert len(pending) == 1


async def test_list_members_by_non_admin_raises(supplier_repo, vector_repo, membership_repo):
    admin_id = uuid4()
    supplier, _ = await _create_supplier(supplier_repo, vector_repo, membership_repo, admin_id)
    joiner_id = uuid4()
    await RequestJoinUseCase(supplier_repo, membership_repo).execute(VALID_RUT, joiner_id)

    with pytest.raises(NotAuthorized):
        await ListMembershipsUseCase(membership_repo).execute(supplier.id, joiner_id, None)


async def test_get_own_membership(supplier_repo, vector_repo, membership_repo):
    admin_id = uuid4()
    supplier, _ = await _create_supplier(supplier_repo, vector_repo, membership_repo, admin_id)

    membership = await GetUserMembershipUseCase(membership_repo).execute(
        admin_id, admin_id
    )
    assert membership.supplier_id == supplier.id


async def test_get_own_membership_when_none_raises(membership_repo):
    user_id = uuid4()
    with pytest.raises(MembershipNotFound):
        await GetUserMembershipUseCase(membership_repo).execute(user_id, user_id)


async def test_admin_can_view_member_membership(supplier_repo, vector_repo, membership_repo):
    admin_id = uuid4()
    await _create_supplier(supplier_repo, vector_repo, membership_repo, admin_id)
    joiner_id = uuid4()
    await RequestJoinUseCase(supplier_repo, membership_repo).execute(VALID_RUT, joiner_id)

    membership = await GetUserMembershipUseCase(membership_repo).execute(
        joiner_id, admin_id
    )
    assert membership.user_id == joiner_id


async def test_non_admin_cannot_view_other_membership(
    supplier_repo, vector_repo, membership_repo
):
    admin_id = uuid4()
    await _create_supplier(supplier_repo, vector_repo, membership_repo, admin_id)
    joiner_id = uuid4()
    await RequestJoinUseCase(supplier_repo, membership_repo).execute(VALID_RUT, joiner_id)

    # El solicitante (no admin) no puede ver la membresía del admin
    with pytest.raises(NotAuthorized):
        await GetUserMembershipUseCase(membership_repo).execute(admin_id, joiner_id)
