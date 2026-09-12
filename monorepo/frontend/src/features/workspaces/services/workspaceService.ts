import { apiFetch } from "@/features/shared/api/client";
import type {
  AcceptInvitationPayload,
  CreateInvitationPayload,
  InvitationDetails,
  SupplierInvitation,
  SwitchWorkspacePayload,
  UserWorkspaceSummary,
  WorkspaceContext,
} from "../types";

export async function listWorkspaces(): Promise<UserWorkspaceSummary[]> {
  return apiFetch<UserWorkspaceSummary[]>("/workspaces");
}

export async function getCurrentWorkspace(): Promise<WorkspaceContext> {
  return apiFetch<WorkspaceContext>("/workspaces/current");
}

export async function switchWorkspace(
  payload: SwitchWorkspacePayload,
): Promise<WorkspaceContext> {
  return apiFetch<WorkspaceContext>("/workspaces/switch", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function createInvitation(
  payload: CreateInvitationPayload,
): Promise<SupplierInvitation> {
  return apiFetch<SupplierInvitation>("/workspaces/invitations", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getMyInvitations(): Promise<SupplierInvitation[]> {
  return apiFetch<SupplierInvitation[]>("/workspaces/invitations/me");
}

export async function verifyInvitation(token: string): Promise<InvitationDetails> {
  return apiFetch<InvitationDetails>(
    `/workspaces/invitations/verify?token=${encodeURIComponent(token)}`,
  );
}

export async function acceptInvitation(
  payload: AcceptInvitationPayload,
): Promise<{ id: string; user_id: string; supplier_id: string; role: string }> {
  return apiFetch<{ id: string; user_id: string; supplier_id: string; role: string }>(
    "/workspaces/invitations/accept",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}
