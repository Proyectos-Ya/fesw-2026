from enum import Enum
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, field_validator

from app.domain.entities.supplier_member import MemberRole
from app.domain.entities.user import is_valid_email
from app.shared.datetime_utils import UtcDateTime, utc_now_naive


class InvitationStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class SupplierInvitation(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    supplier_id: UUID
    email: str
    role: MemberRole = MemberRole.MEMBER
    invited_by_user_id: UUID
    token: str
    status: InvitationStatus = InvitationStatus.PENDING
    expires_at: UtcDateTime
    created_at: UtcDateTime = Field(default_factory=utc_now_naive)
    accepted_at: UtcDateTime | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not is_valid_email(normalized):
            raise ValueError("Email format is invalid")
        return normalized

    def is_expired(self) -> bool:
        if self.status == InvitationStatus.EXPIRED:
            return True
        now = utc_now_naive()
        # Si expires_at no tiene timezone y now tampoco, comparar directamente
        exp = self.expires_at.replace(tzinfo=None) if self.expires_at.tzinfo else self.expires_at
        current = now.replace(tzinfo=None) if now.tzinfo else now
        return current > exp

    def is_pending(self) -> bool:
        return self.status == InvitationStatus.PENDING and not self.is_expired()
