from datetime import timedelta
from uuid import uuid4

import pytest

from app.application.schemas.workspace_schema import CreateInvitationSchema
from app.application.services.email_templates import (
    build_invitation_html_body,
    build_invitation_subject,
    build_invitation_text_body,
    invitation_url,
)
from app.application.use_cases.workspace.accept_supplier_invitation import (
    AcceptSupplierInvitationUseCase,
)
from app.application.use_cases.workspace.cancel_supplier_invitation import (
    CancelSupplierInvitationUseCase,
)
from app.application.use_cases.workspace.create_supplier_invitation import (
    CreateSupplierInvitationUseCase,
)
from app.application.use_cases.workspace.get_invitation_details import (
    GetInvitationDetailsUseCase,
)
from app.application.use_cases.workspace.reject_supplier_invitation import (
    RejectSupplierInvitationUseCase,
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
    InvitationAlreadyPending,
    InvitationAlreadyProcessed,
    InvitationCancelledOrInvalid,
    InvitationEmailMismatch,
    UnauthorizedWorkspaceAction,
    UserAlreadyMember,
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
async def test_ca3_reject_duplicate_invitation_when_already_pending(repos):
    users, suppliers, members, invitations = repos
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

    use_case = CreateSupplierInvitationUseCase(
        invitation_repo=invitations,
        member_repo=members,
        supplier_repo=suppliers,
        user_repo=users,
    )

    # Primera invitación exitosa
    inv1 = await use_case.execute(
        CreateInvitationSchema(
            supplier_id=supplier.id,
            email="nuevo@empresa.cl",
            role=MemberRole.MEMBER,
        ),
        inviter_user_id=admin.id,
    )
    assert inv1.status == InvitationStatus.PENDING

    # Segunda invitación al mismo correo (con mayúsculas/espacios) debe fallar con InvitationAlreadyPending
    with pytest.raises(InvitationAlreadyPending):
        await use_case.execute(
            CreateInvitationSchema(
                supplier_id=supplier.id,
                email="  NUEVO@empresa.cl ",
                role=MemberRole.ADMIN,
            ),
            inviter_user_id=admin.id,
        )


@pytest.mark.asyncio
async def test_ca3_reject_invitation_when_user_already_active_member(repos):
    users, suppliers, members, invitations = repos
    admin = await users.save(
        User(id=uuid4(), email="admin@empresa.cl", full_name="Admin")
    )
    existing_member_user = await users.save(
        User(id=uuid4(), email="miembro@empresa.cl", full_name="Miembro Activo")
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
    await members.save(
        SupplierMember(
            user_id=existing_member_user.id,
            supplier_id=supplier.id,
            role=MemberRole.MEMBER,
            status=MemberStatus.ACTIVE,
        )
    )

    use_case = CreateSupplierInvitationUseCase(
        invitation_repo=invitations,
        member_repo=members,
        supplier_repo=suppliers,
        user_repo=users,
    )

    with pytest.raises(UserAlreadyMember):
        await use_case.execute(
            CreateInvitationSchema(
                supplier_id=supplier.id,
                email="miembro@empresa.cl",
                role=MemberRole.MEMBER,
            ),
            inviter_user_id=admin.id,
        )


@pytest.mark.asyncio
async def test_ca7_admin_can_cancel_pending_invitation_and_non_admin_cannot(repos):
    users, suppliers, members, invitations = repos
    admin = await users.save(
        User(id=uuid4(), email="admin@empresa.cl", full_name="Admin")
    )
    regular = await users.save(
        User(id=uuid4(), email="regular@empresa.cl", full_name="Regular")
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
    await members.save(
        SupplierMember(
            user_id=regular.id,
            supplier_id=supplier.id,
            role=MemberRole.MEMBER,
            status=MemberStatus.ACTIVE,
        )
    )

    inv = await invitations.save(
        SupplierInvitation(
            supplier_id=supplier.id,
            email="invitado@empresa.cl",
            role=MemberRole.MEMBER,
            invited_by_user_id=admin.id,
            token="tok-cancel-test",
            status=InvitationStatus.PENDING,
            expires_at=utc_now_naive() + timedelta(days=7),
        )
    )

    cancel_uc = CancelSupplierInvitationUseCase(
        invitation_repo=invitations,
        member_repo=members,
        supplier_repo=suppliers,
    )

    # Miembro no admin no puede cancelar
    with pytest.raises(UnauthorizedWorkspaceAction):
        await cancel_uc.execute(invitation_id=inv.id, actor_user_id=regular.id)

    # Admin sí puede cancelar
    cancelled = await cancel_uc.execute(invitation_id=inv.id, actor_user_id=admin.id)
    assert cancelled.status == InvitationStatus.CANCELLED

    # Intentar cancelar de nuevo lanza InvitationAlreadyProcessed
    with pytest.raises(InvitationAlreadyProcessed):
        await cancel_uc.execute(invitation_id=inv.id, actor_user_id=admin.id)


@pytest.mark.asyncio
async def test_ca8_cancelled_invitation_is_immediately_invalid_for_verify_and_accept(
    repos,
):
    users, suppliers, members, invitations = repos
    admin = await users.save(
        User(id=uuid4(), email="admin@empresa.cl", full_name="Admin")
    )
    guest = await users.save(
        User(id=uuid4(), email="invitado@empresa.cl", full_name="Invitado")
    )
    supplier = await suppliers.save(
        Supplier(
            id=uuid4(),
            user_id=admin.id,
            rut="76.123.456-0",
            legal_name="Empresa Demo SpA",
        )
    )

    inv = await invitations.save(
        SupplierInvitation(
            supplier_id=supplier.id,
            email="invitado@empresa.cl",
            role=MemberRole.MEMBER,
            invited_by_user_id=admin.id,
            token="tok-cancelled-ca8",
            status=InvitationStatus.CANCELLED,
            expires_at=utc_now_naive() + timedelta(days=7),
        )
    )

    details_uc = GetInvitationDetailsUseCase(
        invitation_repo=invitations,
        supplier_repo=suppliers,
    )
    with pytest.raises(InvitationCancelledOrInvalid):
        await details_uc.execute("tok-cancelled-ca8")

    accept_uc = AcceptSupplierInvitationUseCase(
        invitation_repo=invitations,
        member_repo=members,
    )
    with pytest.raises(InvitationCancelledOrInvalid):
        await accept_uc.execute(token=inv.token, current_user=guest)


@pytest.mark.asyncio
async def test_ca4_recipient_can_reject_pending_invitation(repos):
    users, suppliers, _, invitations = repos
    admin = await users.save(
        User(id=uuid4(), email="admin@empresa.cl", full_name="Admin")
    )
    guest = await users.save(
        User(id=uuid4(), email="invitado@empresa.cl", full_name="Invitado")
    )
    other = await users.save(
        User(id=uuid4(), email="otro@empresa.cl", full_name="Otro")
    )
    supplier = await suppliers.save(
        Supplier(
            id=uuid4(),
            user_id=admin.id,
            rut="76.123.456-0",
            legal_name="Empresa Demo SpA",
        )
    )

    inv = await invitations.save(
        SupplierInvitation(
            supplier_id=supplier.id,
            email="invitado@empresa.cl",
            role=MemberRole.MEMBER,
            invited_by_user_id=admin.id,
            token="tok-reject-ca4",
            status=InvitationStatus.PENDING,
            expires_at=utc_now_naive() + timedelta(days=7),
        )
    )

    reject_uc = RejectSupplierInvitationUseCase(invitation_repo=invitations)

    # Otro usuario no puede rechazar una invitación ajena
    with pytest.raises(InvitationEmailMismatch):
        await reject_uc.execute(token=inv.token, current_user=other)

    # Destinatario rechaza con éxito
    rejected = await reject_uc.execute(token=inv.token, current_user=guest)
    assert rejected.status == InvitationStatus.REJECTED

    # No se puede volver a rechazar una invitación ya rechazada
    with pytest.raises(InvitationAlreadyProcessed):
        await reject_uc.execute(token=inv.token, current_user=guest)


def test_ca2_invitation_email_templates_escape_html_and_include_link():
    subject = build_invitation_subject("Constructora <Andes> SpA")
    assert "Constructora <Andes> SpA" in subject

    url = invitation_url("https://proyectosya.cl/", "tok_abc123")
    assert url == "https://proyectosya.cl/?invitation_token=tok_abc123"

    text_body = build_invitation_text_body(
        supplier_name="Constructora <Andes> SpA",
        inviter_name="Juan <Admin>",
        role=MemberRole.ADMIN,
        base_url="https://proyectosya.cl",
        token="tok_abc123",
    )
    assert "Constructora <Andes> SpA" in text_body
    assert "Administrador" in text_body
    assert url in text_body

    html_body = build_invitation_html_body(
        supplier_name="Constructora <Andes> SpA",
        inviter_name="Juan <Admin>",
        role=MemberRole.ADMIN,
        base_url="https://proyectosya.cl",
        token="tok_abc123",
    )
    assert "Constructora &lt;Andes&gt; SpA" in html_body
    assert "Juan &lt;Admin&gt;" in html_body
    assert "Administrador" in html_body
    assert url in html_body
