import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { CompanyTeamSection } from "../components/CompanyTeamSection";
import * as workspaceService from "@/features/workspaces/services/workspaceService";
import * as workspaceContextModule from "@/features/workspaces/WorkspaceContext";
import { formatDateTime } from "@/features/matches/utils/format";

vi.mock("@/features/workspaces/services/workspaceService", () => ({
  listWorkspaceMembers: vi.fn(),
  listWorkspaceInvitations: vi.fn(),
  createInvitation: vi.fn(),
  cancelInvitation: vi.fn(),
  revokeWorkspaceMember: vi.fn(),
}));

vi.mock("@/features/workspaces/WorkspaceContext", () => ({
  useWorkspace: vi.fn(),
}));

const mockMembers = [
  {
    id: "m-admin",
    user_id: "u-admin",
    supplier_id: "sup-1",
    email: "admin@empresa.cl",
    full_name: "Ana Administradora",
    role: "admin" as const,
    status: "active" as const,
    last_access_at: "2026-09-28T14:00:00Z",
    joined_at: "2026-09-01T10:00:00Z",
  },
  {
    id: "m-rep",
    user_id: "u-rep",
    supplier_id: "sup-1",
    email: "rep@empresa.cl",
    full_name: "Roberto Representante",
    role: "member" as const,
    status: "active" as const,
    last_access_at: "2026-09-28T16:45:00Z",
    joined_at: "2026-09-10T10:00:00Z",
  },
];

function buildWorkspaceMock(isAdmin: boolean, userId: string) {
  return {
    workspaces: [],
    recentWorkspaces: [],
    activeWorkspace: {
      user_id: userId,
      active_supplier_id: "sup-1",
      active_supplier_name: "Constructora del Pacífico SpA",
      role: isAdmin ? ("admin" as const) : ("member" as const),
      permissions: isAdmin ? ["invite_members", "remove_members"] : ["view_matches"],
      is_admin: isAdmin,
    },
    invitations: [],
    isLoading: false,
    isAdmin,
    hasPermission: () => isAdmin,
    switchActiveWorkspace: vi.fn(),
    refreshWorkspaces: vi.fn(),
    refreshInvitations: vi.fn(),
    acceptPendingInvitation: vi.fn(),
    rejectPendingInvitation: vi.fn(),
  };
}

describe("CompanyTeamSection (HU-13)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(workspaceService.listWorkspaceMembers).mockResolvedValue(
      mockMembers,
    );
    vi.mocked(workspaceService.listWorkspaceInvitations).mockResolvedValue([]);
  });

  it("CA1 y CA4: muestra la fecha/hora de último acceso formateada y deshabilita 'Revocar acceso' para el propio administrador", async () => {
    vi.mocked(workspaceContextModule.useWorkspace).mockReturnValue(
      buildWorkspaceMock(true, "u-admin"),
    );

    render(
      <CompanyTeamSection
        supplierId="sup-1"
        supplierName="Constructora del Pacífico SpA"
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("Ana Administradora")).toBeInTheDocument();
      expect(screen.getByText("Roberto Representante")).toBeInTheDocument();
    });

    // CA1: Columna de Último acceso y fechas formateadas visibles
    expect(screen.getByText("Último acceso")).toBeInTheDocument();
    expect(
      screen.getByText(formatDateTime("2026-09-28T14:00:00Z")),
    ).toBeInTheDocument();
    expect(
      screen.getByText(formatDateTime("2026-09-28T16:45:00Z")),
    ).toBeInTheDocument();

    // CA4: El botón del propio administrador está deshabilitado y el del representante habilitado
    const adminRevokeBtn = screen.getByRole("button", {
      name: /Revocar acceso de Ana Administradora/i,
    });
    const repRevokeBtn = screen.getByRole("button", {
      name: /Revocar acceso de Roberto Representante/i,
    });

    expect(adminRevokeBtn).toBeDisabled();
    expect(repRevokeBtn).not.toBeDisabled();
  });

  it("CA2: permite al administrador revocar el acceso de un representante con diálogo de confirmación y notificación", async () => {
    vi.mocked(workspaceContextModule.useWorkspace).mockReturnValue(
      buildWorkspaceMock(true, "u-admin"),
    );
    vi.mocked(workspaceService.revokeWorkspaceMember).mockResolvedValueOnce({
      id: "m-rep",
      user_id: "u-rep",
      supplier_id: "sup-1",
      role: "member",
      status: "inactive",
    });

    render(
      <CompanyTeamSection
        supplierId="sup-1"
        supplierName="Constructora del Pacífico SpA"
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("Roberto Representante")).toBeInTheDocument();
    });

    const repRevokeBtn = screen.getByRole("button", {
      name: /Revocar acceso de Roberto Representante/i,
    });
    fireEvent.click(repRevokeBtn);

    // Diálogo de confirmación visible
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(
      screen.getByText(/¿Revocar acceso al equipo\?/i),
    ).toBeInTheDocument();

    const confirmBtn = screen.getByRole("button", {
      name: /Confirmar revocación/i,
    });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(workspaceService.revokeWorkspaceMember).toHaveBeenCalledWith(
        "sup-1",
        "m-rep",
      );
    });

    // El miembro revocado desaparece de la tabla y se muestra notificación
    await waitFor(() => {
      expect(
        screen.queryByText("Roberto Representante"),
      ).not.toBeInTheDocument();
      expect(screen.getByRole("status")).toHaveTextContent(
        /Acceso de Roberto Representante revocado correctamente/i,
      );
    });
  });

  it("CA5: el representante ve la tabla del equipo en modo lectura sin columna de acciones ni botones de revocación", async () => {
    vi.mocked(workspaceContextModule.useWorkspace).mockReturnValue(
      buildWorkspaceMock(false, "u-rep"),
    );

    render(
      <CompanyTeamSection
        supplierId="sup-1"
        supplierName="Constructora del Pacífico SpA"
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("Ana Administradora")).toBeInTheDocument();
      expect(screen.getByText("Roberto Representante")).toBeInTheDocument();
    });

    // Ve la columna de Último acceso
    expect(screen.getByText("Último acceso")).toBeInTheDocument();

    // No ve botones de revocar acceso ni formulario de invitación
    expect(
      screen.queryByRole("button", { name: /Revocar acceso/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Enviar invitación/i }),
    ).not.toBeInTheDocument();
  });
});
