from enum import Enum
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

from app.shared.datetime_utils import UtcDateTime, utc_now_naive


class MemberRole(str, Enum):
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class MemberStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


_ROLE_PERMISSIONS: dict[MemberRole, set[str]] = {
    MemberRole.ADMIN: {
        "invite_members",
        "remove_members",
        "edit_company_profile",
        "manage_tenders",
        "view_matches",
        "save_tenders",
        "chat_assistant",
        "deep_analysis",
    },
    MemberRole.MEMBER: {
        "view_matches",
        "save_tenders",
        "chat_assistant",
        "deep_analysis",
    },
    MemberRole.VIEWER: {
        "view_matches",
    },
}


class SupplierMember(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    supplier_id: UUID
    role: MemberRole = MemberRole.MEMBER
    status: MemberStatus = MemberStatus.ACTIVE
    created_at: UtcDateTime = Field(default_factory=utc_now_naive)
    updated_at: UtcDateTime = Field(default_factory=utc_now_naive)

    def is_admin(self) -> bool:
        return self.status == MemberStatus.ACTIVE and self.role == MemberRole.ADMIN

    def has_permission(self, permission: str) -> bool:
        if self.status != MemberStatus.ACTIVE:
            return False
        return permission in _ROLE_PERMISSIONS.get(self.role, set())


class WorkspaceContext(BaseModel):
    user_id: UUID
    active_supplier_id: UUID
    active_supplier_name: str
    role: MemberRole
    permissions: list[str] = Field(default_factory=list)
    is_admin: bool = False


class UserWorkspaceSummary(BaseModel):
    supplier_id: UUID
    legal_name: str
    trade_name: str | None = None
    rut: str
    role: MemberRole
    status: MemberStatus = MemberStatus.ACTIVE
    is_active_context: bool = False
