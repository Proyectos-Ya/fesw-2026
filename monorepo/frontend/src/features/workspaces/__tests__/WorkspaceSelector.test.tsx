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
      activeWorkspace: null,
      invitations: [],
      isLoading: false,
      isAdmin: false,
      hasPermission: vi.fn(),
      switchActiveWorkspace: mockSwitch,
      refreshWorkspaces: vi.fn(),
      refreshInvitations: vi.fn(),
      acceptPendingInvitation: vi.fn(),
    });

    render(<WorkspaceSelector />);
    expect(screen.getByText("Registrar empresa")).toBeInTheDocument();
  });

  it("renderiza el espacio de trabajo activo con su rol (Admin)", () => {
    vi.spyOn(WorkspaceContextModule, "useWorkspace").mockReturnValue({
      workspaces: mockWorkspaces,
      activeWorkspace: mockActiveWorkspace,
      invitations: [],
      isLoading: false,
      isAdmin: true,
      hasPermission: vi.fn(),
      switchActiveWorkspace: mockSwitch,
      refreshWorkspaces: vi.fn(),
      refreshInvitations: vi.fn(),
      acceptPendingInvitation: vi.fn(),
    });

    render(<WorkspaceSelector />);
    expect(screen.getByText("Alfa")).toBeInTheDocument();
    expect(screen.getByText("Admin")).toBeInTheDocument();
    expect(screen.getByText("76.111.111-1")).toBeInTheDocument();
  });

  it("despliega la lista de espacios de trabajo al hacer clic y permite conmutar", async () => {
    vi.spyOn(WorkspaceContextModule, "useWorkspace").mockReturnValue({
      workspaces: mockWorkspaces,
      activeWorkspace: mockActiveWorkspace,
      invitations: [],
      isLoading: false,
      isAdmin: true,
      hasPermission: vi.fn(),
      switchActiveWorkspace: mockSwitch,
      refreshWorkspaces: vi.fn(),
      refreshInvitations: vi.fn(),
      acceptPendingInvitation: vi.fn(),
    });

    render(<WorkspaceSelector />);

    const triggerBtn = screen.getByRole("button", {
      name: "Seleccionar espacio de trabajo",
    });
    fireEvent.click(triggerBtn);

    expect(screen.getByText("Espacios de trabajo")).toBeInTheDocument();
    expect(screen.getByText("Beta")).toBeInTheDocument();

    const betaBtn = screen.getByText("Beta").closest("button");
    expect(betaBtn).not.toBeNull();
    fireEvent.click(betaBtn!);

    await waitFor(() => {
      expect(mockSwitch).toHaveBeenCalledWith("s-2");
    });
  });
});
