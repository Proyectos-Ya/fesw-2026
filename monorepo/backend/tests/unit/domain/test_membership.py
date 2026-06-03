from uuid import uuid4

from app.domain.entities.membership import (
    MembershipRole,
    MembershipStatus,
    SupplierMembership,
)


def test_create_membership_defaults_to_pending():
    membership = SupplierMembership(
        user_id=uuid4(),
        supplier_id=uuid4(),
    )
    # Por defecto una solicitud nace pendiente y sin fecha de ingreso
    assert membership.status == MembershipStatus.PENDING
    assert membership.role == MembershipRole.MEMBER
    assert membership.joined_at is None


def test_create_admin_membership():
    membership = SupplierMembership(
        user_id=uuid4(),
        supplier_id=uuid4(),
        role=MembershipRole.ADMIN,
        status=MembershipStatus.ACTIVE,
    )
    assert membership.role == MembershipRole.ADMIN
    assert membership.status == MembershipStatus.ACTIVE
