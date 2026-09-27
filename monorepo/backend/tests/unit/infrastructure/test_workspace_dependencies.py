from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
import pytest
from fastapi import HTTPException

from app.application.repositories.supplier_member_repository import (
    ISupplierMemberRepository,
)
from app.application.repositories.supplier_repository import ISupplierRepository
from app.domain.entities.supplier import Supplier
from app.domain.entities.supplier_member import (
    MemberRole,
    MemberStatus,
    SupplierMember,
    WorkspaceContext,
)
from app.domain.entities.user import User
from app.infrastructure.auth.dependencies import (
    build_get_current_workspace_context,
)


@pytest.fixture
def mock_user() -> User:
    return User(
        id=uuid4(),
        email="test@user.cl",
        hashed_password="hash",
        full_name="Test User",
    )


@pytest.fixture
def mock_supplier() -> Supplier:
    return Supplier(
        id=uuid4(),
        rut="76.123.456-0",
        legal_name="Empresa Test SpA",
        trade_name="Test Trade",
    )




@pytest.mark.asyncio
async def test_workspace_context_from_header_admin(
    mock_user: User, mock_supplier: Supplier
):
    member_repo = MagicMock(spec=ISupplierMemberRepository)
    supplier_repo = MagicMock(spec=ISupplierRepository)

    member = SupplierMember(
        user_id=mock_user.id,
        supplier_id=mock_supplier.id,
        role=MemberRole.ADMIN,
        status=MemberStatus.ACTIVE,
    )
    member_repo.get_by_user_and_supplier = AsyncMock(return_value=member)
    supplier_repo.get_by_id = AsyncMock(return_value=mock_supplier)

    get_context = build_get_current_workspace_context(
        get_current_user=lambda: mock_user,
        get_member_repo=lambda: member_repo,
        get_supplier_repo=lambda: supplier_repo,
    )

    request = MagicMock()
    request.headers = {"X-Workspace-Id": str(mock_supplier.id)}
    request.cookies = {}

    context: WorkspaceContext = await get_context(
        request=request,
        current_user=mock_user,
        member_repo=member_repo,
        supplier_repo=supplier_repo,
    )

    assert context.user_id == mock_user.id
    assert context.active_supplier_id == mock_supplier.id
    assert context.active_supplier_name == "Test Trade"
    assert context.role == MemberRole.ADMIN
    assert context.is_admin is True
    assert "invite_members" in context.permissions


@pytest.mark.asyncio
async def test_workspace_context_forbidden_if_not_member(
    mock_user: User, mock_supplier: Supplier
):
    member_repo = MagicMock(spec=ISupplierMemberRepository)
    supplier_repo = MagicMock(spec=ISupplierRepository)

    member_repo.get_by_user_and_supplier = AsyncMock(return_value=None)
    supplier_repo.get_by_id = AsyncMock(return_value=mock_supplier)

    get_context = build_get_current_workspace_context(
        get_current_user=lambda: mock_user,
        get_member_repo=lambda: member_repo,
        get_supplier_repo=lambda: supplier_repo,
    )

    request = MagicMock()
    request.headers = {"X-Workspace-Id": str(mock_supplier.id)}
    request.cookies = {}

    with pytest.raises(HTTPException) as exc_info:
        await get_context(
            request=request,
            current_user=mock_user,
            member_repo=member_repo,
            supplier_repo=supplier_repo,
        )

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_workspace_context_fallback_default_workspace(
    mock_user: User, mock_supplier: Supplier
):
    member_repo = MagicMock(spec=ISupplierMemberRepository)
    supplier_repo = MagicMock(spec=ISupplierRepository)

    member = SupplierMember(
        user_id=mock_user.id,
        supplier_id=mock_supplier.id,
        role=MemberRole.MEMBER,
        status=MemberStatus.ACTIVE,
    )
    member_repo.list_by_user_id = AsyncMock(return_value=[member])
    member_repo.get_by_user_and_supplier = AsyncMock(return_value=member)
    supplier_repo.get_by_id = AsyncMock(return_value=mock_supplier)

    get_context = build_get_current_workspace_context(
        get_current_user=lambda: mock_user,
        get_member_repo=lambda: member_repo,
        get_supplier_repo=lambda: supplier_repo,
    )

    request = MagicMock()
    request.headers = {}
    request.cookies = {}

    context = await get_context(
        request=request,
        current_user=mock_user,
        member_repo=member_repo,
        supplier_repo=supplier_repo,
    )

    assert context.active_supplier_id == mock_supplier.id
    assert context.role == MemberRole.MEMBER
    assert context.is_admin is False
    assert "view_matches" in context.permissions
    assert "invite_members" not in context.permissions
