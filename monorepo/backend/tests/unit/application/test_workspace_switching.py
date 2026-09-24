from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
import pytest

from app.application.repositories.supplier_member_repository import (
    ISupplierMemberRepository,
)
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.schemas.workspace_schema import SwitchWorkspaceSchema
from app.application.use_cases.workspace.switch_workspace import (
    SwitchWorkspaceUseCase,
)
from app.domain.entities.supplier import Supplier
from app.domain.entities.supplier_member import (
    MemberRole,
    MemberStatus,
    SupplierMember,
    WorkspaceContext,
)
from app.domain.entities.user import User
from app.domain.errors.membership_errors import (
    MembershipNotFound,
    UnauthorizedWorkspaceAction,
)
from app.domain.errors.supplier_errors import SupplierNotFound


@pytest.fixture
def mock_user() -> User:
    return User(
        id=uuid4(),
        email="test@user.cl",
        hashed_password="hash",
        full_name="Usuario Multi",
    )


@pytest.fixture
def mock_company_a() -> Supplier:
    return Supplier(
        id=uuid4(),
        rut="76.123.456-0",
        legal_name="Empresa A SpA",
        trade_name="Empresa A",
    )


@pytest.fixture
def mock_company_b() -> Supplier:
    return Supplier(
        id=uuid4(),
        rut="77.654.321-7",
        legal_name="Empresa B Ltda",
        trade_name="Empresa B",
    )


@pytest.mark.asyncio
async def test_switch_workspace_recalculates_admin_role_and_permissions(
    mock_user: User, mock_company_a: Supplier
):
    member_repo = MagicMock(spec=ISupplierMemberRepository)
    supplier_repo = MagicMock(spec=ISupplierRepository)

    admin_member = SupplierMember(
        user_id=mock_user.id,
        supplier_id=mock_company_a.id,
        role=MemberRole.ADMIN,
        status=MemberStatus.ACTIVE,
    )
    member_repo.get_by_user_and_supplier = AsyncMock(return_value=admin_member)
    supplier_repo.get_by_id = AsyncMock(return_value=mock_company_a)

    use_case = SwitchWorkspaceUseCase(
        member_repo=member_repo,
        supplier_repo=supplier_repo,
    )

    context = await use_case.execute(
        current_user=mock_user,
        data=SwitchWorkspaceSchema(supplier_id=mock_company_a.id),
    )

    assert context.user_id == mock_user.id
    assert context.active_supplier_id == mock_company_a.id
    assert context.active_supplier_name == "Empresa A"
    assert context.role == MemberRole.ADMIN
    assert context.is_admin is True
    assert "invite_members" in context.permissions
    assert "edit_company_profile" in context.permissions


@pytest.mark.asyncio
async def test_switch_workspace_recalculates_member_role_and_permissions(
    mock_user: User, mock_company_b: Supplier
):
    member_repo = MagicMock(spec=ISupplierMemberRepository)
    supplier_repo = MagicMock(spec=ISupplierRepository)

    regular_member = SupplierMember(
        user_id=mock_user.id,
        supplier_id=mock_company_b.id,
        role=MemberRole.MEMBER,
        status=MemberStatus.ACTIVE,
    )
    member_repo.get_by_user_and_supplier = AsyncMock(return_value=regular_member)
    supplier_repo.get_by_id = AsyncMock(return_value=mock_company_b)

    use_case = SwitchWorkspaceUseCase(
        member_repo=member_repo,
        supplier_repo=supplier_repo,
    )

    context = await use_case.execute(
        current_user=mock_user,
        data=SwitchWorkspaceSchema(supplier_id=mock_company_b.id),
    )

    assert context.user_id == mock_user.id
    assert context.active_supplier_id == mock_company_b.id
    assert context.active_supplier_name == "Empresa B"
    assert context.role == MemberRole.MEMBER
    assert context.is_admin is False
    assert "invite_members" not in context.permissions
    assert "view_matches" in context.permissions


@pytest.mark.asyncio
async def test_switch_workspace_unauthorized_if_not_member(
    mock_user: User, mock_company_a: Supplier
):
    member_repo = MagicMock(spec=ISupplierMemberRepository)
    supplier_repo = MagicMock(spec=ISupplierRepository)

    member_repo.get_by_user_and_supplier = AsyncMock(return_value=None)
    supplier_repo.get_by_id = AsyncMock(return_value=mock_company_a)

    use_case = SwitchWorkspaceUseCase(
        member_repo=member_repo,
        supplier_repo=supplier_repo,
    )

    with pytest.raises(UnauthorizedWorkspaceAction):
        await use_case.execute(
            current_user=mock_user,
            data=SwitchWorkspaceSchema(supplier_id=mock_company_a.id),
        )


@pytest.mark.asyncio
async def test_switch_workspace_forbidden_if_inactive_member(
    mock_user: User, mock_company_a: Supplier
):
    member_repo = MagicMock(spec=ISupplierMemberRepository)
    supplier_repo = MagicMock(spec=ISupplierRepository)

    inactive_member = SupplierMember(
        user_id=mock_user.id,
        supplier_id=mock_company_a.id,
        role=MemberRole.ADMIN,
        status=MemberStatus.INACTIVE,
    )
    member_repo.get_by_user_and_supplier = AsyncMock(return_value=inactive_member)
    supplier_repo.get_by_id = AsyncMock(return_value=mock_company_a)

    use_case = SwitchWorkspaceUseCase(
        member_repo=member_repo,
        supplier_repo=supplier_repo,
    )

    with pytest.raises(UnauthorizedWorkspaceAction):
        await use_case.execute(
            current_user=mock_user,
            data=SwitchWorkspaceSchema(supplier_id=mock_company_a.id),
        )
