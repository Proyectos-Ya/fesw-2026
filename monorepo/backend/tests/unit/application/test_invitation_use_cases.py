from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
import pytest

from app.application.repositories.supplier_invitation_repository import (
    ISupplierInvitationRepository,
)
from app.application.repositories.supplier_member_repository import (
    ISupplierMemberRepository,
)
from app.application.repositories.supplier_repository import ISupplierRepository
from app.application.schemas.workspace_schema import CreateInvitationSchema
from app.application.use_cases.workspace.accept_supplier_invitation import (
    AcceptSupplierInvitationUseCase,
)
from app.application.use_cases.workspace.create_supplier_invitation import (
    CreateSupplierInvitationUseCase,
)
from app.application.use_cases.workspace.get_invitation_details import (
    GetInvitationDetailsUseCase,
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
    InvitationAlreadyProcessed,
    InvitationEmailMismatch,
    InvitationExpired,
    InvitationNotFound,
    UnauthorizedWorkspaceAction,
    UserAlreadyMember,
)
from app.shared.datetime_utils import utc_now_naive


@pytest.fixture
def mock_admin_user() -> User:
    return User(
        id=uuid4(),
        email="admin@empresa.cl",
        hashed_password="hash",
        full_name="Admin Usuario",
    )


@pytest.fixture
def mock_invited_user() -> User:
    return User(
        id=uuid4(),
        email="colaborador@externo.cl",
        hashed_password="hash",
        full_name="Colaborador Externo",
    )


@pytest.fixture
def mock_supplier() -> Supplier:
    return Supplier(
        id=uuid4(),
        rut="76.123.456-0",
        legal_name="Empresa Principal SpA",
        trade_name="Principal",
    )


@pytest.mark.asyncio
async def test_create_invitation_success(
    mock_admin_user: User, mock_supplier: Supplier
):
    invitation_repo = MagicMock(spec=ISupplierInvitationRepository)
    member_repo = MagicMock(spec=ISupplierMemberRepository)
    supplier_repo = MagicMock(spec=ISupplierRepository)

    # El usuario que invita es admin
    admin_member = SupplierMember(
        user_id=mock_admin_user.id,
        supplier_id=mock_supplier.id,
        role=MemberRole.ADMIN,
        status=MemberStatus.ACTIVE,
    )
    member_repo.get_by_user_and_supplier = AsyncMock(return_value=admin_member)
    supplier_repo.get_by_id = AsyncMock(return_value=mock_supplier)
    invitation_repo.save = AsyncMock(side_effect=lambda inv: inv)

    use_case = CreateSupplierInvitationUseCase(
        invitation_repo=invitation_repo,
        member_repo=member_repo,
        supplier_repo=supplier_repo,
    )

    dto = CreateInvitationSchema(
        supplier_id=mock_supplier.id,
        email="colaborador@externo.cl",
        role=MemberRole.MEMBER,
    )

    result = await use_case.execute(dto, inviter_user_id=mock_admin_user.id)

    assert result.supplier_id == mock_supplier.id
    assert result.email == "colaborador@externo.cl"
    assert result.role == MemberRole.MEMBER
    assert result.status == InvitationStatus.PENDING
    assert result.token is not None
    invitation_repo.save.assert_called_once()


@pytest.mark.asyncio
async def test_create_invitation_unauthorized_if_not_admin(
    mock_admin_user: User, mock_supplier: Supplier
):
    invitation_repo = MagicMock(spec=ISupplierInvitationRepository)
    member_repo = MagicMock(spec=ISupplierMemberRepository)
    supplier_repo = MagicMock(spec=ISupplierRepository)

    # Es solo un miembro común, no puede invitar
    regular_member = SupplierMember(
        user_id=mock_admin_user.id,
        supplier_id=mock_supplier.id,
        role=MemberRole.MEMBER,
        status=MemberStatus.ACTIVE,
    )
    member_repo.get_by_user_and_supplier = AsyncMock(return_value=regular_member)
    supplier_repo.get_by_id = AsyncMock(return_value=mock_supplier)

    use_case = CreateSupplierInvitationUseCase(
        invitation_repo=invitation_repo,
        member_repo=member_repo,
        supplier_repo=supplier_repo,
    )

    dto = CreateInvitationSchema(
        supplier_id=mock_supplier.id,
        email="colaborador@externo.cl",
        role=MemberRole.MEMBER,
    )

    with pytest.raises(UnauthorizedWorkspaceAction):
        await use_case.execute(dto, inviter_user_id=mock_admin_user.id)


@pytest.mark.asyncio
async def test_get_invitation_details(mock_supplier: Supplier):
    invitation_repo = MagicMock(spec=ISupplierInvitationRepository)
    supplier_repo = MagicMock(spec=ISupplierRepository)

    invitation = SupplierInvitation(
        supplier_id=mock_supplier.id,
        email="colaborador@externo.cl",
        role=MemberRole.MEMBER,
        invited_by_user_id=uuid4(),
        token="token_abc_123",
        status=InvitationStatus.PENDING,
        expires_at=utc_now_naive() + timedelta(days=7),
    )
    invitation_repo.get_by_token = AsyncMock(return_value=invitation)
    supplier_repo.get_by_id = AsyncMock(return_value=mock_supplier)

    use_case = GetInvitationDetailsUseCase(invitation_repo, supplier_repo)
    details = await use_case.execute("token_abc_123")

    assert details.supplier_id == mock_supplier.id
    assert details.supplier_name == "Principal"
    assert details.email == "colaborador@externo.cl"


@pytest.mark.asyncio
async def test_accept_invitation_success_for_existing_user(
    mock_invited_user: User, mock_supplier: Supplier
):
    invitation_repo = MagicMock(spec=ISupplierInvitationRepository)
    member_repo = MagicMock(spec=ISupplierMemberRepository)
    supplier_repo = MagicMock(spec=ISupplierRepository)

    invitation = SupplierInvitation(
        supplier_id=mock_supplier.id,
        email=mock_invited_user.email,
        role=MemberRole.MEMBER,
        invited_by_user_id=uuid4(),
        token="token_valid_123",
        status=InvitationStatus.PENDING,
        expires_at=utc_now_naive() + timedelta(days=7),
    )
    invitation_repo.get_by_token = AsyncMock(return_value=invitation)
    invitation_repo.update = AsyncMock(side_effect=lambda inv: inv)
    member_repo.get_by_user_and_supplier = AsyncMock(return_value=None)
    member_repo.save = AsyncMock(side_effect=lambda m: m)

    use_case = AcceptSupplierInvitationUseCase(
        invitation_repo=invitation_repo,
        member_repo=member_repo,
    )

    membership = await use_case.execute(
        token="token_valid_123", current_user=mock_invited_user
    )

    assert membership.user_id == mock_invited_user.id
    assert membership.supplier_id == mock_supplier.id
    assert membership.role == MemberRole.MEMBER
    assert membership.status == MemberStatus.ACTIVE

    assert invitation.status == InvitationStatus.ACCEPTED
    assert invitation.accepted_at is not None
    invitation_repo.update.assert_called_once()
    member_repo.save.assert_called_once()


@pytest.mark.asyncio
async def test_accept_invitation_email_mismatch_fails(
    mock_supplier: Supplier,
):
    invitation_repo = MagicMock(spec=ISupplierInvitationRepository)
    member_repo = MagicMock(spec=ISupplierMemberRepository)

    invitation = SupplierInvitation(
        supplier_id=mock_supplier.id,
        email="otro_correo@empresa.cl",
        role=MemberRole.MEMBER,
        invited_by_user_id=uuid4(),
        token="token_valid_123",
        status=InvitationStatus.PENDING,
        expires_at=utc_now_naive() + timedelta(days=7),
    )
    invitation_repo.get_by_token = AsyncMock(return_value=invitation)

    current_user = User(
        id=uuid4(),
        email="distinto@usuario.cl",
        hashed_password="hash",
        full_name="Usuario Distinto",
    )

    use_case = AcceptSupplierInvitationUseCase(
        invitation_repo=invitation_repo,
        member_repo=member_repo,
    )

    with pytest.raises(InvitationEmailMismatch):
        await use_case.execute(token="token_valid_123", current_user=current_user)


@pytest.mark.asyncio
async def test_accept_invitation_expired_fails(
    mock_invited_user: User, mock_supplier: Supplier
):
    invitation_repo = MagicMock(spec=ISupplierInvitationRepository)
    member_repo = MagicMock(spec=ISupplierMemberRepository)

    invitation = SupplierInvitation(
        supplier_id=mock_supplier.id,
        email=mock_invited_user.email,
        role=MemberRole.MEMBER,
        invited_by_user_id=uuid4(),
        token="token_expired_123",
        status=InvitationStatus.PENDING,
        expires_at=utc_now_naive() - timedelta(days=1),
    )
    invitation_repo.get_by_token = AsyncMock(return_value=invitation)

    use_case = AcceptSupplierInvitationUseCase(
        invitation_repo=invitation_repo,
        member_repo=member_repo,
    )

    with pytest.raises(InvitationExpired):
        await use_case.execute(
            token="token_expired_123", current_user=mock_invited_user
        )
