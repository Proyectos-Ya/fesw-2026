import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { WorkspaceSelector } from "../components/WorkspaceSelector";
import * as WorkspaceContextModule from "../WorkspaceContext";
import type { UserWorkspaceSummary, WorkspaceContext } from "../types";

describe("WorkspaceSelector", () => {
  const mockSwitch = vi.fn();

  const mockWorkspaces: UserWorkspaceSummary[] = [
    {
      supplier_id: "s-1",
      legal_name: "Empresa Alfa SpA",
      trade_name: "Alfa",
      rut: "76.111.111-1",
      role: "admin",
      status: "active",
      is_active_context: true,
    },
    {
      supplier_id: "s-2",
      legal_name: "Empresa Beta Ltda",
      trade_name: "Beta",
      rut: "77.222.222-2",
      role: "member",
      status: "active",
      is_active_context: false,
    },
  ];

  const mockActiveWorkspace: WorkspaceContext = {
    user_id: "u-1",
    active_supplier_id: "s-1",
    active_supplier_name: "Alfa",
    role: "admin",
    permissions: ["invite_members"],
    is_admin: true,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renderiza botón de registrar empresa si el usuario no tiene ninguna", () => {
    vi.spyOn(WorkspaceContextModule, "useWorkspace").mockReturnValue({
      workspaces: [],
      recentWorkspaces: [],
      activeWorkspace: null,
      invitations: [],
      isLoading: false,
      isAdmin: false,
      hasPermission: vi.fn(),
      switchActiveWorkspace: mockSwitch,
      refreshWorkspaces: vi.fn(),
      refreshInvitations: vi.fn(),
      acceptPendingInvitation: vi.fn(),
      rejectPendingInvitation: vi.fn(),
    });

    render(<WorkspaceSelector />);
    expect(screen.getByText("Registrar empresa")).toBeInTheDocument();
  });

  it("renderiza el espacio de trabajo activo con su rol (Admin)", () => {
    vi.spyOn(WorkspaceContextModule, "useWorkspace").mockReturnValue({
      workspaces: mockWorkspaces,
      recentWorkspaces: [],
      activeWorkspace: mockActiveWorkspace,
      invitations: [],
      isLoading: false,
      isAdmin: true,
      hasPermission: vi.fn(),
      switchActiveWorkspace: mockSwitch,
      refreshWorkspaces: vi.fn(),
      refreshInvitations: vi.fn(),
      acceptPendingInvitation: vi.fn(),
      rejectPendingInvitation: vi.fn(),
    });

    render(<WorkspaceSelector />);
    expect(screen.getByText("Alfa")).toBeInTheDocument();
    expect(screen.getByText("Admin")).toBeInTheDocument();
    expect(screen.getByText("76.111.111-1")).toBeInTheDocument();
  });

  it("despliega la lista de espacios de trabajo al hacer clic y permite conmutar", async () => {
    vi.spyOn(WorkspaceContextModule, "useWorkspace").mockReturnValue({
      workspaces: mockWorkspaces,
      recentWorkspaces: [],
      activeWorkspace: mockActiveWorkspace,
      invitations: [],
      isLoading: false,
      isAdmin: true,
      hasPermission: vi.fn(),
      switchActiveWorkspace: mockSwitch,
      refreshWorkspaces: vi.fn(),
      refreshInvitations: vi.fn(),
      acceptPendingInvitation: vi.fn(),
      rejectPendingInvitation: vi.fn(),
    });

    render(<WorkspaceSelector />);

    const triggerBtn = screen.getByRole("button", {
      name: "Seleccionar espacio de trabajo",
    });
    fireEvent.click(triggerBtn);

    expect(screen.getByText("Espacios de trabajo")).toBeInTheDocument();
    expect(screen.getByText("Beta")).toBeInTheDocument();
    expect(screen.getByText("Representante")).toBeInTheDocument();

    const betaBtn = screen.getByText("Beta").closest("button");
    expect(betaBtn).not.toBeNull();
    fireEvent.click(betaBtn!);

    await waitFor(() => {
      expect(mockSwitch).toHaveBeenCalledWith("s-2");
    });
  });

  it("muestra indicador y enlace a invitaciones pendientes cuando el usuario tiene invitaciones (multi-empresa)", () => {
    vi.spyOn(WorkspaceContextModule, "useWorkspace").mockReturnValue({
      workspaces: mockWorkspaces,
      recentWorkspaces: [],
      activeWorkspace: mockActiveWorkspace,
      invitations: [
        {
          id: "inv-ws-1",
          supplier_id: "s-3",
          supplier_name: "Nueva Empresa SpA",
          supplier_rut: "78.333.333-3",
          invited_by: "u-2",
          email: "user@test.cl",
          role: "member",
          token: "tok-3",
          status: "pending",
          expires_at: "2026-10-10",
          created_at: "2026-10-01",
        },
      ],
      isLoading: false,
      isAdmin: true,
      hasPermission: vi.fn(),
      switchActiveWorkspace: mockSwitch,
      refreshWorkspaces: vi.fn(),
      refreshInvitations: vi.fn(),
      acceptPendingInvitation: vi.fn(),
      rejectPendingInvitation: vi.fn(),
    });

    render(<WorkspaceSelector />);

    // El botón cerrado no debe tener badge para evitar saturar la barra lateral
    expect(screen.queryByTestId("invitations-badge")).not.toBeInTheDocument();

    // Al abrir el dropdown, debe mostrarse el acceso directo a invitaciones pendientes
    const triggerBtn = screen.getByRole("button", {
      name: "Seleccionar espacio de trabajo",
    });
    fireEvent.click(triggerBtn);

    expect(screen.getByText("Invitaciones pendientes (1)")).toBeInTheDocument();
  });
});
