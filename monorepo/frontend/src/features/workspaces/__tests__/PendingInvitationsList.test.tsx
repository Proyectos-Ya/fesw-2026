import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { PendingInvitationsList } from "../components/PendingInvitationsList";
import * as WorkspaceContextModule from "../WorkspaceContext";
import type { SupplierInvitation } from "../types";

describe("PendingInvitationsList", () => {
  const mockAccept = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("no renderiza nada si la lista de invitaciones está vacía", () => {
    vi.spyOn(WorkspaceContextModule, "useWorkspace").mockReturnValue({
      workspaces: [],
      activeWorkspace: null,
      invitations: [],
      isLoading: false,
      isAdmin: false,
      hasPermission: vi.fn(),
      switchActiveWorkspace: vi.fn(),
      refreshWorkspaces: vi.fn(),
      refreshInvitations: vi.fn(),
      acceptPendingInvitation: mockAccept,
    });

    const { container } = render(<PendingInvitationsList />);
    expect(container.firstChild).toBeNull();
  });

  it("renderiza invitaciones pendientes y permite aceptarlas", async () => {
    const mockInvitations: SupplierInvitation[] = [
      {
        id: "inv-1",
        supplier_id: "s-1",
        invited_by: "u-1",
        email: "user@test.cl",
        role: "admin",
        token: "tok-123",
        status: "pending",
        expires_at: "2026-10-01",
        created_at: "2026-09-12T10:00:00Z",
      },
    ];

    vi.spyOn(WorkspaceContextModule, "useWorkspace").mockReturnValue({
      workspaces: [],
      activeWorkspace: null,
      invitations: mockInvitations,
      isLoading: false,
      isAdmin: false,
      hasPermission: vi.fn(),
      switchActiveWorkspace: vi.fn(),
      refreshWorkspaces: vi.fn(),
      refreshInvitations: vi.fn(),
      acceptPendingInvitation: mockAccept,
    });

    render(<PendingInvitationsList />);

    expect(
      screen.getByText("Invitaciones a espacios de trabajo (1)"),
    ).toBeInTheDocument();
    expect(screen.getByText("Administrador")).toBeInTheDocument();

    const acceptBtn = screen.getByRole("button", { name: "Aceptar invitación" });
    fireEvent.click(acceptBtn);

    await waitFor(() => {
      expect(mockAccept).toHaveBeenCalledWith("tok-123");
    });
  });
});
