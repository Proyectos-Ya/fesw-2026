import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { GlobalInvitationsBanner } from "../components/GlobalInvitationsBanner";
import * as WorkspaceContextModule from "../WorkspaceContext";
import type { SupplierInvitation } from "../types";

let mockPathname = "/empresa";
vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname,
}));

const mockInvitation1: SupplierInvitation = {
  id: "inv-global-1",
  supplier_id: "sup-global-1",
  supplier_name: "Constructora Andes SpA",
  supplier_rut: "76.123.456-7",
  invited_by: "u-admin",
  email: "usuario@empresa.cl",
  role: "member",
  token: "tok-global-1",
  status: "pending",
  expires_at: "2026-10-15T00:00:00Z",
  created_at: "2026-10-01T10:00:00Z",
};

const mockInvitation2: SupplierInvitation = {
  id: "inv-global-2",
  supplier_id: "sup-global-2",
  supplier_name: "Minera del Norte Ltda",
  supplier_rut: "77.987.654-3",
  invited_by: "u-admin-2",
  email: "usuario@empresa.cl",
  role: "member",
  token: "tok-global-2",
  status: "pending",
  expires_at: "2026-10-20T00:00:00Z",
  created_at: "2026-10-02T10:00:00Z",
};

describe("GlobalInvitationsBanner", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockPathname = "/empresa";
  });

  it("no renderiza nada si no hay invitaciones pendientes", () => {
    vi.spyOn(WorkspaceContextModule, "useWorkspace").mockReturnValue({
      workspaces: [],
      recentWorkspaces: [],
      activeWorkspace: null,
      invitations: [],
      isLoading: false,
      isAdmin: false,
      hasPermission: () => false,
      switchActiveWorkspace: vi.fn(),
      refreshWorkspaces: vi.fn(),
      refreshInvitations: vi.fn(),
      acceptPendingInvitation: vi.fn(),
      rejectPendingInvitation: vi.fn(),
    });

    const { container } = render(<GlobalInvitationsBanner />);
    expect(container.firstChild).toBeNull();
  });

  it("no renderiza nada en la ruta /workspaces para evitar duplicación con la pantalla completa", () => {
    mockPathname = "/workspaces";
    vi.spyOn(WorkspaceContextModule, "useWorkspace").mockReturnValue({
      workspaces: [],
      recentWorkspaces: [],
      activeWorkspace: null,
      invitations: [mockInvitation1],
      isLoading: false,
      isAdmin: false,
      hasPermission: () => false,
      switchActiveWorkspace: vi.fn(),
      refreshWorkspaces: vi.fn(),
      refreshInvitations: vi.fn(),
      acceptPendingInvitation: vi.fn(),
      rejectPendingInvitation: vi.fn(),
    });

    const { container } = render(<GlobalInvitationsBanner />);
    expect(container.firstChild).toBeNull();
  });

  it("renderiza el banner global con el nombre de la empresa y enlace a revisar cuando el usuario está en cualquier otra página (/empresa, /buscar, etc.)", () => {
    mockPathname = "/empresa";
    vi.spyOn(WorkspaceContextModule, "useWorkspace").mockReturnValue({
      workspaces: [
        {
          supplier_id: "sup-actual",
          legal_name: "Empresa Actual SpA",
          trade_name: "Actual",
          rut: "76.000.000-1",
          role: "admin",
          status: "active",
          is_active_context: true,
        },
      ],
      recentWorkspaces: [],
      activeWorkspace: {
        user_id: "u-1",
        active_supplier_id: "sup-actual",
        active_supplier_name: "Actual",
        role: "admin",
        permissions: [],
        is_admin: true,
      },
      invitations: [mockInvitation1],
      isLoading: false,
      isAdmin: true,
      hasPermission: () => true,
      switchActiveWorkspace: vi.fn(),
      refreshWorkspaces: vi.fn(),
      refreshInvitations: vi.fn(),
      acceptPendingInvitation: vi.fn(),
      rejectPendingInvitation: vi.fn(),
    });

    render(<GlobalInvitationsBanner />);

    expect(screen.getByText(/Tienes una invitación pendiente/i)).toBeInTheDocument();
    expect(screen.getByText("Constructora Andes SpA")).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /revisar invitaciones/i });
    expect(link).toHaveAttribute("href", "/workspaces");
  });

  it("renderiza el conteo en plural cuando hay más de una invitación", () => {
    mockPathname = "/buscar";
    vi.spyOn(WorkspaceContextModule, "useWorkspace").mockReturnValue({
      workspaces: [],
      recentWorkspaces: [],
      activeWorkspace: null,
      invitations: [mockInvitation1, mockInvitation2],
      isLoading: false,
      isAdmin: false,
      hasPermission: () => false,
      switchActiveWorkspace: vi.fn(),
      refreshWorkspaces: vi.fn(),
      refreshInvitations: vi.fn(),
      acceptPendingInvitation: vi.fn(),
      rejectPendingInvitation: vi.fn(),
    });

    render(<GlobalInvitationsBanner />);

    expect(screen.getByText(/Tienes 2 invitaciones pendientes/i)).toBeInTheDocument();
  });
});
