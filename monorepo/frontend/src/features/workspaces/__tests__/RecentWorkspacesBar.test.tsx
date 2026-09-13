import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { RecentWorkspacesBar } from "../components/RecentWorkspacesBar";
import * as WorkspaceContextModule from "../WorkspaceContext";
import type { UserWorkspaceSummary, WorkspaceContext } from "../types";

describe("RecentWorkspacesBar", () => {
  const mockSwitch = vi.fn();

  const mockRecentWorkspaces: UserWorkspaceSummary[] = [
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
    {
      supplier_id: "s-3",
      legal_name: "Empresa Gamma SA",
      trade_name: "Gamma",
      rut: "78.333.333-3",
      role: "viewer",
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

  it("no renderiza nada si está cargando o no hay workspaces recientes", () => {
    vi.spyOn(WorkspaceContextModule, "useWorkspace").mockReturnValue({
      workspaces: [],
      recentWorkspaces: [],
      activeWorkspace: null,
      invitations: [],
      isLoading: true,
      isAdmin: false,
      hasPermission: vi.fn(),
      switchActiveWorkspace: mockSwitch,
      refreshWorkspaces: vi.fn(),
      refreshInvitations: vi.fn(),
      acceptPendingInvitation: vi.fn(),
    });

    const { container } = render(<RecentWorkspacesBar />);
    expect(container.firstChild).toBeNull();
  });

  it("renderiza tarjetas de workspaces recientes con nombre, RUT e indicador de Activo", () => {
    vi.spyOn(WorkspaceContextModule, "useWorkspace").mockReturnValue({
      workspaces: mockRecentWorkspaces,
      recentWorkspaces: mockRecentWorkspaces,
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

    render(<RecentWorkspacesBar />);

    expect(screen.getByText("Espacios de trabajo recientes")).toBeInTheDocument();
    expect(screen.getByText("Alfa")).toBeInTheDocument();
    expect(screen.getByText("Beta")).toBeInTheDocument();
    expect(screen.getByText("Gamma")).toBeInTheDocument();

    expect(screen.getByText("76.111.111-1")).toBeInTheDocument();
    expect(screen.getByText("77.222.222-2")).toBeInTheDocument();
    expect(screen.getByText("78.333.333-3")).toBeInTheDocument();

    expect(screen.getByText("Activo")).toBeInTheDocument();
  });

  it("llama a switchActiveWorkspace al hacer clic en un workspace no activo", () => {
    vi.spyOn(WorkspaceContextModule, "useWorkspace").mockReturnValue({
      workspaces: mockRecentWorkspaces,
      recentWorkspaces: mockRecentWorkspaces,
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

    render(<RecentWorkspacesBar />);

    const betaButton = screen.getByText("Beta").closest("button");
    expect(betaButton).not.toBeNull();
    fireEvent.click(betaButton!);

    expect(mockSwitch).toHaveBeenCalledWith("s-2");
  });

  it("no llama a switchActiveWorkspace si se hace clic en el workspace ya activo", () => {
    vi.spyOn(WorkspaceContextModule, "useWorkspace").mockReturnValue({
      workspaces: mockRecentWorkspaces,
      recentWorkspaces: mockRecentWorkspaces,
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

    render(<RecentWorkspacesBar />);

    const alfaButton = screen.getByText("Alfa").closest("button");
    expect(alfaButton).not.toBeNull();
    fireEvent.click(alfaButton!);

    expect(mockSwitch).not.toHaveBeenCalled();
  });
});
