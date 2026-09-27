from uuid import uuid4
import pytest
from app.domain.entities.supplier_member import (
    MemberRole,
    MemberStatus,
    SupplierMember,
    WorkspaceContext,
    UserWorkspaceSummary,
)


def test_supplier_member_creation_defaults():
    user_id = uuid4()
    supplier_id = uuid4()
    member = SupplierMember(user_id=user_id, supplier_id=supplier_id)

    assert member.user_id == user_id
    assert member.supplier_id == supplier_id
    assert member.role == MemberRole.MEMBER
    assert member.status == MemberStatus.ACTIVE
    assert not member.is_admin()
    assert member.created_at is not None
    assert member.updated_at is not None


def test_supplier_member_admin_permissions():
    user_id = uuid4()
    supplier_id = uuid4()
    admin_member = SupplierMember(
        user_id=user_id,
        supplier_id=supplier_id,
        role=MemberRole.ADMIN,
    )

    assert admin_member.is_admin() is True
    assert admin_member.has_permission("invite_members") is True
    assert admin_member.has_permission("edit_company_profile") is True
    assert admin_member.has_permission("manage_tenders") is True
    assert admin_member.has_permission("view_matches") is True


def test_supplier_member_regular_member_permissions():
    user_id = uuid4()
    supplier_id = uuid4()
    regular_member = SupplierMember(
        user_id=user_id,
        supplier_id=supplier_id,
        role=MemberRole.MEMBER,
    )

    assert regular_member.is_admin() is False
    assert regular_member.has_permission("invite_members") is False
    assert regular_member.has_permission("edit_company_profile") is False
    assert regular_member.has_permission("view_matches") is True
    assert regular_member.has_permission("save_tenders") is True


def test_supplier_member_viewer_permissions():
    user_id = uuid4()
    supplier_id = uuid4()
    viewer_member = SupplierMember(
        user_id=user_id,
        supplier_id=supplier_id,
        role=MemberRole.VIEWER,
    )

    assert viewer_member.is_admin() is False
    assert viewer_member.has_permission("invite_members") is False
    assert viewer_member.has_permission("edit_company_profile") is False
    assert viewer_member.has_permission("view_matches") is True
    assert viewer_member.has_permission("save_tenders") is False


def test_supplier_member_inactive_denies_all_permissions():
    user_id = uuid4()
    supplier_id = uuid4()
    inactive_admin = SupplierMember(
        user_id=user_id,
        supplier_id=supplier_id,
        role=MemberRole.ADMIN,
        status=MemberStatus.INACTIVE,
    )

    assert inactive_admin.has_permission("view_matches") is False
    assert inactive_admin.has_permission("invite_members") is False


def test_workspace_context_creation():
    user_id = uuid4()
    supplier_id = uuid4()
    context = WorkspaceContext(
        user_id=user_id,
        active_supplier_id=supplier_id,
        active_supplier_name="Mi Empresa SpA",
        role=MemberRole.ADMIN,
        permissions=["invite_members", "edit_company_profile"],
        is_admin=True,
    )

    assert context.user_id == user_id
    assert context.active_supplier_id == supplier_id
    assert context.active_supplier_name == "Mi Empresa SpA"
    assert context.role == MemberRole.ADMIN
    assert context.is_admin is True
    assert "invite_members" in context.permissions


def test_user_workspace_summary():
    supplier_id = uuid4()
    summary = UserWorkspaceSummary(
        supplier_id=supplier_id,
        legal_name="Empresa A",
        trade_name="Empresa A Fantasia",
        rut="76123456-7",
        role=MemberRole.ADMIN,
        status=MemberStatus.ACTIVE,
        is_active_context=True,
    )

    assert summary.supplier_id == supplier_id
    assert summary.legal_name == "Empresa A"
    assert summary.is_active_context is True
