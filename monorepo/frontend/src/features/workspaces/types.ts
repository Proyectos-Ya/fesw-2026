export type MemberRole = "admin" | "member" | "viewer";
export type MemberStatus = "active" | "inactive" | "suspended";
export type InvitationStatus =
  | "pending"
  | "accepted"
  | "rejected"
  | "expired"
  | "cancelled"
  | "revoked";

export interface UserWorkspaceSummary {
  supplier_id: string;
  legal_name: string;
  trade_name: string | null;
  rut: string;
  role: MemberRole;
  status: MemberStatus;
  is_active_context: boolean;
}

export interface WorkspaceContext {
  user_id: string;
  active_supplier_id: string;
  active_supplier_name: string;
  role: MemberRole;
  permissions: string[];
  is_admin: boolean;
}

export interface SupplierInvitation {
  id: string;
  supplier_id: string;
  supplier_name?: string;
  supplier_rut?: string;
  invited_by: string;
  email: string;
  role: MemberRole;
  token: string;
  status: InvitationStatus;
  expires_at: string;
  created_at: string;
}

export interface WorkspaceMemberSummary {
  id: string;
  user_id: string;
  supplier_id: string;
  role: MemberRole;
  status: MemberStatus;
  last_access_at?: string | null;
  created_at?: string | null;
}

export interface WorkspaceMemberDetail {
  id: string;
  user_id: string;
  supplier_id: string;
  email: string;
  full_name: string;
  role: MemberRole;
  status: MemberStatus;
  last_access_at?: string | null;
  joined_at?: string | null;
  created_at?: string | null;
}

export interface InvitationDetails {
  id: string;
  supplier_id: string;
  supplier_name: string;
  supplier_rut: string;
  invited_by_name: string;
  email: string;
  role: MemberRole;
  expires_at: string;
}

export interface CreateInvitationPayload {
  supplier_id: string;
  email: string;
  role: MemberRole;
}

export interface AcceptInvitationPayload {
  token: string;
}

export interface RejectInvitationPayload {
  token: string;
}

export interface SwitchWorkspacePayload {
  supplier_id: string;
}
