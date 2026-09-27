from datetime import timedelta
from uuid import uuid4
import pytest
from app.domain.entities.supplier_invitation import (
    InvitationStatus,
    SupplierInvitation,
)
from app.domain.entities.supplier_member import MemberRole
from app.shared.datetime_utils import utc_now_naive


def test_supplier_invitation_creation_and_defaults():
    supplier_id = uuid4()
    invited_by = uuid4()
    expires_at = utc_now_naive() + timedelta(days=7)

    invitation = SupplierInvitation(
        supplier_id=supplier_id,
        email="colaborador@empresa.cl",
        role=MemberRole.MEMBER,
        invited_by_user_id=invited_by,
        token="token_seguro_123456",
        expires_at=expires_at,
    )

    assert invitation.supplier_id == supplier_id
    assert invitation.email == "colaborador@empresa.cl"
    assert invitation.role == MemberRole.MEMBER
    assert invitation.invited_by_user_id == invited_by
    assert invitation.status == InvitationStatus.PENDING
    assert invitation.is_pending() is True
    assert invitation.is_expired() is False


def test_supplier_invitation_expired():
    supplier_id = uuid4()
    invited_by = uuid4()
    expires_at = utc_now_naive() - timedelta(days=1)

    invitation = SupplierInvitation(
        supplier_id=supplier_id,
        email="colaborador@empresa.cl",
        role=MemberRole.MEMBER,
        invited_by_user_id=invited_by,
        token="token_seguro_123456",
        expires_at=expires_at,
    )

    assert invitation.is_expired() is True
    assert invitation.is_pending() is False
