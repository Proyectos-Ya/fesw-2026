import { describe, it, expect, vi, beforeEach } from "vitest";
import * as client from "@/features/shared/api/client";
import {
  acceptInvitation,
  cancelInvitation,
  clearActiveWorkspace,
  createInvitation,
  getCurrentWorkspace,
  getMyInvitations,
  listWorkspaceInvitations,
  listWorkspaceMembers,
  listWorkspaces,
  rejectInvitation,
  revokeWorkspaceMember,
  switchWorkspace,
  verifyInvitation,
} from "../services/workspaceService";

vi.mock("@/features/shared/api/client", () => ({
  apiFetch: vi.fn(),
  ApiError: class ApiError extends Error {
    constructor(public status: number, message: string) {
      super(message);
    }
  },
}));

describe("workspaceService", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("listWorkspaces llama a GET /workspaces", async () => {
    const mockData = [
      {
        supplier_id: "s-1",
        legal_name: "Empresa Uno SpA",
        trade_name: "Empresa Uno",
        rut: "76.123.456-0",
        role: "admin",
        status: "active",
        is_active_context: true,
      },
    ];
    vi.mocked(client.apiFetch).mockResolvedValueOnce(mockData);

    const result = await listWorkspaces();
    expect(client.apiFetch).toHaveBeenCalledWith("/workspaces");
    expect(result).toEqual(mockData);
  });

  it("getCurrentWorkspace llama a GET /workspaces/current", async () => {
    const mockContext = {
      user_id: "u-1",
      active_supplier_id: "s-1",
      active_supplier_name: "Empresa Uno",
      role: "admin",
      permissions: ["invite_members", "view_matches"],
      is_admin: true,
    };
    vi.mocked(client.apiFetch).mockResolvedValueOnce(mockContext);

    const result = await getCurrentWorkspace();
    expect(client.apiFetch).toHaveBeenCalledWith("/workspaces/current");
    expect(result).toEqual(mockContext);
  });

  it("switchWorkspace llama a POST /workspaces/switch con el supplier_id", async () => {
    const mockResponse = {
      user_id: "u-1",
      active_supplier_id: "s-2",
      active_supplier_name: "Empresa Dos",
      role: "member",
      permissions: ["view_matches"],
      is_admin: false,
    };
    vi.mocked(client.apiFetch).mockResolvedValueOnce(mockResponse);

    const result = await switchWorkspace({ supplier_id: "s-2" });
    expect(client.apiFetch).toHaveBeenCalledWith("/workspaces/switch", {
      method: "POST",
      body: JSON.stringify({ supplier_id: "s-2" }),
    });
    expect(result).toEqual(mockResponse);
  });

  it("createInvitation llama a POST /workspaces/invitations", async () => {
    const payload = {
      supplier_id: "s-1",
      email: "colleague@test.cl",
      role: "member" as const,
    };
    const mockInvitation = {
      id: "inv-1",
      supplier_id: "s-1",
      invited_by: "u-1",
      email: "colleague@test.cl",
      role: "member" as const,
      token: "tok-123",
      status: "pending" as const,
      expires_at: "2026-10-01T00:00:00Z",
      created_at: "2026-09-12T00:00:00Z",
    };
    vi.mocked(client.apiFetch).mockResolvedValueOnce(mockInvitation);

    const result = await createInvitation(payload);
    expect(client.apiFetch).toHaveBeenCalledWith("/workspaces/invitations", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    expect(result).toEqual(mockInvitation);
  });

  it("getMyInvitations llama a GET /workspaces/invitations/me", async () => {
    vi.mocked(client.apiFetch).mockResolvedValueOnce([]);
    const result = await getMyInvitations();
    expect(client.apiFetch).toHaveBeenCalledWith("/workspaces/invitations/me");
    expect(result).toEqual([]);
  });

  it("verifyInvitation llama a GET /workspaces/invitations/verify con token codificado", async () => {
    vi.mocked(client.apiFetch).mockResolvedValueOnce({
      id: "inv-1",
      supplier_id: "s-1",
      supplier_name: "Empresa Uno",
      supplier_rut: "76.123.456-0",
      invited_by_name: "Admin",
      email: "test@user.cl",
      role: "member",
      expires_at: "2026-10-01",
    });

    await verifyInvitation("tok-xyz 123");
    expect(client.apiFetch).toHaveBeenCalledWith(
      "/workspaces/invitations/verify?token=tok-xyz%20123",
    );
  });

  it("acceptInvitation llama a POST /workspaces/invitations/accept", async () => {
    const mockMember = {
      id: "m-1",
      user_id: "u-1",
      supplier_id: "s-1",
      role: "member",
    };
    vi.mocked(client.apiFetch).mockResolvedValueOnce(mockMember);

    const result = await acceptInvitation({ token: "tok-123" });
    expect(client.apiFetch).toHaveBeenCalledWith("/workspaces/invitations/accept", {
      method: "POST",
      body: JSON.stringify({ token: "tok-123" }),
    });
    expect(result).toEqual(mockMember);
  });

  it("rejectInvitation llama a POST /workspaces/invitations/reject", async () => {
    const mockRejected = {
      id: "inv-1",
      supplier_id: "s-1",
      invited_by: "u-1",
      email: "colleague@test.cl",
      role: "member" as const,
      token: "tok-123",
      status: "rejected" as const,
      expires_at: "2026-10-01T00:00:00Z",
      created_at: "2026-09-12T00:00:00Z",
    };
    vi.mocked(client.apiFetch).mockResolvedValueOnce(mockRejected);

    const result = await rejectInvitation({ token: "tok-123" });
    expect(client.apiFetch).toHaveBeenCalledWith("/workspaces/invitations/reject", {
      method: "POST",
      body: JSON.stringify({ token: "tok-123" }),
    });
    expect(result).toEqual(mockRejected);
  });

  it("cancelInvitation llama a DELETE /workspaces/invitations/{id}", async () => {
    const mockCancelled = {
      id: "inv-99",
      supplier_id: "s-1",
      invited_by: "u-1",
      email: "colleague@test.cl",
      role: "member" as const,
      token: "tok-99",
      status: "cancelled" as const,
      expires_at: "2026-10-01T00:00:00Z",
      created_at: "2026-09-12T00:00:00Z",
    };
    vi.mocked(client.apiFetch).mockResolvedValueOnce(mockCancelled);

    const result = await cancelInvitation("inv-99");
    expect(client.apiFetch).toHaveBeenCalledWith("/workspaces/invitations/inv-99", {
      method: "DELETE",
    });
    expect(result).toEqual(mockCancelled);
  });

  it("listWorkspaceMembers llama a GET /workspaces/{supplierId}/members", async () => {
    const mockMembers = [
      {
        id: "m-1",
        user_id: "u-1",
        supplier_id: "s-1",
        email: "admin@empresa.cl",
        full_name: "Admin Uno",
        role: "admin" as const,
        status: "active" as const,
        last_access_at: "2026-09-28T15:30:00Z",
        joined_at: "2026-09-01T00:00:00Z",
      },
    ];
    vi.mocked(client.apiFetch).mockResolvedValueOnce(mockMembers);

    const result = await listWorkspaceMembers("s-1");
    expect(client.apiFetch).toHaveBeenCalledWith("/workspaces/s-1/members");
    expect(result).toEqual(mockMembers);
  });

  it("listWorkspaceInvitations llama a GET /workspaces/{supplierId}/invitations", async () => {
    const mockPending = [
      {
        id: "inv-2",
        supplier_id: "s-1",
        invited_by: "u-1",
        email: "pendiente@empresa.cl",
        role: "member" as const,
        token: "tok-2",
        status: "pending" as const,
        expires_at: "2026-10-01T00:00:00Z",
        created_at: "2026-09-12T00:00:00Z",
      },
    ];
    vi.mocked(client.apiFetch).mockResolvedValueOnce(mockPending);

    const result = await listWorkspaceInvitations("s-1");
    expect(client.apiFetch).toHaveBeenCalledWith("/workspaces/s-1/invitations");
    expect(result).toEqual(mockPending);
  });

  it("revokeWorkspaceMember llama a DELETE /workspaces/{supplierId}/members/{memberId} (HU-13 CA2)", async () => {
    const mockRevoked = {
      id: "m-2",
      user_id: "u-2",
      supplier_id: "s-1",
      role: "member" as const,
      status: "inactive" as const,
    };
    vi.mocked(client.apiFetch).mockResolvedValueOnce(mockRevoked);

    const result = await revokeWorkspaceMember("s-1", "m-2");
    expect(client.apiFetch).toHaveBeenCalledWith("/workspaces/s-1/members/m-2", {
      method: "DELETE",
    });
    expect(result).toEqual(mockRevoked);
  });

  it("clearActiveWorkspace llama a POST /workspaces/clear-active (HU-13 CA3)", async () => {
    vi.mocked(client.apiFetch).mockResolvedValueOnce(undefined);

    await clearActiveWorkspace();
    expect(client.apiFetch).toHaveBeenCalledWith("/workspaces/clear-active", {
      method: "POST",
    });
  });
});
