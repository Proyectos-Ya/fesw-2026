from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.entities.supplier_invitation import InvitationStatus
from app.domain.entities.supplier_member import MemberRole, MemberStatus


class CreateInvitationSchema(BaseModel):
    supplier_id: UUID
    email: str = Field(max_length=255)
    role: MemberRole = MemberRole.MEMBER


class AcceptInvitationSchema(BaseModel):
    token: str = Field(min_length=1)


class RejectInvitationSchema(BaseModel):
    token: str = Field(min_length=1)


class InvitationDetailsSchema(BaseModel):
    id: UUID
    supplier_id: UUID
    supplier_name: str
    email: str
    role: MemberRole
    status: InvitationStatus
    expires_at: datetime
    created_at: datetime


class UserPendingInvitationSchema(BaseModel):
    id: UUID
    supplier_id: UUID
    supplier_name: str = ""
    supplier_rut: str = ""
    invited_by_user_id: UUID
    invited_by_name: str | None = None
    email: str
    role: MemberRole
    token: str
    status: InvitationStatus
    expires_at: datetime
    created_at: datetime
    accepted_at: datetime | None = None


class WorkspaceMemberSummarySchema(BaseModel):
    id: UUID
    user_id: UUID
    supplier_id: UUID
    role: MemberRole
    status: MemberStatus
    last_access_at: datetime | None = None
    created_at: datetime


class WorkspaceMemberDetailSchema(BaseModel):
    id: UUID
    user_id: UUID
    supplier_id: UUID
    full_name: str
    email: str
    role: MemberRole
    status: MemberStatus
    last_access_at: datetime | None = None
    created_at: datetime


class SwitchWorkspaceSchema(BaseModel):
    supplier_id: UUID
