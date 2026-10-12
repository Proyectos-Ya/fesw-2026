import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ApiError } from "@/features/shared/api/client";
import { PendingInvitationsList } from "../components/PendingInvitationsList";
import * as WorkspaceContextModule from "../WorkspaceContext";
import type { SupplierInvitation } from "../types";

describe("PendingInvitationsList", () => {
  const mockAccept = vi.fn();
  const mockReject = vi.fn();
  const mockRefreshInvitations = vi.fn();

  const sampleInvitation: SupplierInvitation = {
    id: "inv-1",
    supplier_id: "s-1",
    supplier_name: "Constructora Austral SpA",
    supplier_rut: "76.123.456-0",
    invited_by: "u-1",
    email: "user@test.cl",
    role: "admin",
    token: "tok-123",
    status: "pending",
    expires_at: "2026-10-01",
    created_at: "2026-09-12T10:00:00Z",
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("no renderiza nada si la lista de invitaciones está vacía", () => {
    vi.spyOn(WorkspaceContextModule, "useWorkspace").mockReturnValue({
      workspaces: [],
      recentWorkspaces: [],
      activeWorkspace: null,
      invitations: [],
      isLoading: false,
      isAdmin: false,
      hasPermission: vi.fn(),
      switchActiveWorkspace: vi.fn(),
      refreshWorkspaces: vi.fn(),
      refreshInvitations: mockRefreshInvitations,
      acceptPendingInvitation: mockAccept,
      rejectPendingInvitation: mockReject,
    });

    const { container } = render(<PendingInvitationsList />);
    expect(container.firstChild).toBeNull();
  });

  it("renderiza el nombre de la empresa y botones Aceptar y Rechazar para usuario sin organización (CA4)", async () => {
    vi.spyOn(WorkspaceContextModule, "useWorkspace").mockReturnValue({
      workspaces: [],
      recentWorkspaces: [],
      activeWorkspace: null,
      invitations: [sampleInvitation],
      isLoading: false,
      isAdmin: false,
      hasPermission: vi.fn(),
      switchActiveWorkspace: vi.fn(),
      refreshWorkspaces: vi.fn(),
      refreshInvitations: mockRefreshInvitations,
      acceptPendingInvitation: mockAccept,
      rejectPendingInvitation: mockReject,
    });

    render(<PendingInvitationsList />);

    expect(
      screen.getByText("Invitaciones a espacios de trabajo (1)"),
    ).toBeInTheDocument();
    expect(screen.getByText(/Constructora Austral SpA/)).toBeInTheDocument();
    expect(screen.getByText("Administrador")).toBeInTheDocument();

    const acceptBtn = screen.getByRole("button", { name: /aceptar invitación/i });
    const rejectBtn = screen.getByRole("button", { name: /rechazar/i });
    expect(acceptBtn).toBeInTheDocument();
    expect(rejectBtn).toBeInTheDocument();

    fireEvent.click(acceptBtn);

    await waitFor(() => {
      expect(mockAccept).toHaveBeenCalledWith("tok-123");
    });
  });

  it("muestra aviso de conservación de membresías cuando el usuario ya pertenece a otras organizaciones (CA5)", () => {
    vi.spyOn(WorkspaceContextModule, "useWorkspace").mockReturnValue({
      workspaces: [
        {
          supplier_id: "s-prev",
          legal_name: "Empresa Previa Ltda",
          trade_name: "Previa",
          rut: "77.654.321-7",
          role: "admin",
          status: "active",
          is_active_context: true,
        },
      ],
      recentWorkspaces: [],
      activeWorkspace: {
        user_id: "u-2",
        active_supplier_id: "s-prev",
        active_supplier_name: "Previa",
        role: "admin",
        permissions: ["invite_members"],
        is_admin: true,
      },
      invitations: [sampleInvitation],
      isLoading: false,
      isAdmin: true,
      hasPermission: vi.fn(),
      switchActiveWorkspace: vi.fn(),
      refreshWorkspaces: vi.fn(),
      refreshInvitations: mockRefreshInvitations,
      acceptPendingInvitation: mockAccept,
      rejectPendingInvitation: mockReject,
    });

    render(<PendingInvitationsList />);

    expect(
      screen.getByText(/sin perder tus membresías actuales/i),
    ).toBeInTheDocument();
  });

  it("permite rechazar una invitación pendiente invocando rejectPendingInvitation (CA4, CA5)", async () => {
    vi.spyOn(WorkspaceContextModule, "useWorkspace").mockReturnValue({
      workspaces: [],
      recentWorkspaces: [],
      activeWorkspace: null,
      invitations: [sampleInvitation],
      isLoading: false,
      isAdmin: false,
      hasPermission: vi.fn(),
      switchActiveWorkspace: vi.fn(),
      refreshWorkspaces: vi.fn(),
      refreshInvitations: mockRefreshInvitations,
      acceptPendingInvitation: mockAccept,
      rejectPendingInvitation: mockReject,
    });

    render(<PendingInvitationsList />);

    const rejectBtn = screen.getByRole("button", { name: /rechazar/i });
    fireEvent.click(rejectBtn);

    await waitFor(() => {
      expect(mockReject).toHaveBeenCalledWith("tok-123");
    });
  });

  it("captura error 410 Gone si la invitación fue cancelada por el admin, muestra alerta y retira la invitación (CA8)", async () => {
    mockAccept.mockRejectedValueOnce(
      new ApiError(
        410,
        "Esta invitación fue cancelada por el administrador y ya no es válida.",
      ),
    );

    vi.spyOn(WorkspaceContextModule, "useWorkspace").mockReturnValue({
      workspaces: [],
      recentWorkspaces: [],
      activeWorkspace: null,
      invitations: [sampleInvitation],
      isLoading: false,
      isAdmin: false,
      hasPermission: vi.fn(),
      switchActiveWorkspace: vi.fn(),
      refreshWorkspaces: vi.fn(),
      refreshInvitations: mockRefreshInvitations,
      acceptPendingInvitation: mockAccept,
      rejectPendingInvitation: mockReject,
    });

    render(<PendingInvitationsList />);

    fireEvent.click(screen.getByRole("button", { name: /aceptar invitación/i }));

    expect(
      await screen.findByText(
        "Esta invitación fue cancelada por el administrador y ya no es válida.",
      ),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(
        screen.queryByRole("button", { name: /aceptar invitación/i }),
      ).not.toBeInTheDocument();
    });
    expect(mockRefreshInvitations).toHaveBeenCalled();
  });

  it("muestra el rol Representante cuando la invitación es para un miembro no administrador", () => {
    const memberInvitation: SupplierInvitation = {
      ...sampleInvitation,
      id: "inv-rep-1",
      role: "member",
    };

    vi.spyOn(WorkspaceContextModule, "useWorkspace").mockReturnValue({
      workspaces: [],
      recentWorkspaces: [],
      activeWorkspace: null,
      invitations: [memberInvitation],
      isLoading: false,
      isAdmin: false,
      hasPermission: vi.fn(),
      switchActiveWorkspace: vi.fn(),
      refreshWorkspaces: vi.fn(),
      refreshInvitations: mockRefreshInvitations,
      acceptPendingInvitation: mockAccept,
      rejectPendingInvitation: mockReject,
    });

    render(<PendingInvitationsList />);
    expect(screen.getByText("Representante")).toBeInTheDocument();
  });
});
