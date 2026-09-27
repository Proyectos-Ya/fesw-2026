import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { ApiError } from "@/features/shared/api/client";
import * as WorkspaceContextModule from "@/features/workspaces/WorkspaceContext";
import * as workspaceService from "@/features/workspaces/services/workspaceService";
import { CompanyTeamSection } from "../CompanyTeamSection";

vi.mock("@/features/workspaces/services/workspaceService", () => ({
  listWorkspaceMembers: vi.fn(),
  listWorkspaceInvitations: vi.fn(),
  createInvitation: vi.fn(),
  cancelInvitation: vi.fn(),
}));

const baseWorkspaceContext = {
  workspaces: [],
  recentWorkspaces: [],
  activeWorkspace: {
    user_id: "u-admin",
    active_supplier_id: "sup-1",
    active_supplier_name: "Constructora Norte SpA",
    role: "admin" as const,
    permissions: ["invite_members", "manage_workspace"],
    is_admin: true,
  },
  invitations: [],
  isLoading: false,
  isAdmin: true,
  hasPermission: () => true,
  switchActiveWorkspace: vi.fn(),
  refreshWorkspaces: vi.fn(),
  refreshInvitations: vi.fn(),
  acceptPendingInvitation: vi.fn(),
  rejectPendingInvitation: vi.fn(),
};

describe("CompanyTeamSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("no renderiza nada cuando el usuario no es administrador (CA1)", () => {
    vi.spyOn(WorkspaceContextModule, "useWorkspace").mockReturnValue({
      ...baseWorkspaceContext,
      isAdmin: false,
      activeWorkspace: {
        ...baseWorkspaceContext.activeWorkspace,
        role: "member",
        is_admin: false,
      },
    });

    const { container } = render(
      <CompanyTeamSection
        supplierId="sup-1"
        supplierName="Constructora Norte SpA"
      />,
    );

    expect(container.firstChild).toBeNull();
    expect(workspaceService.listWorkspaceMembers).not.toHaveBeenCalled();
  });

  it("muestra miembros actuales, invitaciones pendientes y formulario para el administrador (CA1)", async () => {
    vi.spyOn(WorkspaceContextModule, "useWorkspace").mockReturnValue(
      baseWorkspaceContext,
    );
    vi.mocked(workspaceService.listWorkspaceMembers).mockResolvedValueOnce([
      {
        id: "m-1",
        user_id: "u-admin",
        supplier_id: "sup-1",
        email: "admin@norte.cl",
        full_name: "Ana Administradora",
        role: "admin",
        status: "active",
        joined_at: "2026-09-01T10:00:00Z",
      },
      {
        id: "m-2",
        user_id: "u-rep",
        supplier_id: "sup-1",
        email: "rep@norte.cl",
        full_name: "Roberto Representante",
        role: "member",
        status: "active",
        joined_at: "2026-09-05T10:00:00Z",
      },
    ]);
    vi.mocked(workspaceService.listWorkspaceInvitations).mockResolvedValueOnce([
      {
        id: "inv-1",
        supplier_id: "sup-1",
        invited_by: "u-admin",
        email: "pendiente@norte.cl",
        role: "member",
        token: "tok-1",
        status: "pending",
        expires_at: "2026-10-01T00:00:00Z",
        created_at: "2026-09-10T10:00:00Z",
      },
    ]);

    render(
      <CompanyTeamSection
        supplierId="sup-1"
        supplierName="Constructora Norte SpA"
      />,
    );

    expect(
      await screen.findByText("Ana Administradora"),
    ).toBeInTheDocument();
    expect(screen.getByText("admin@norte.cl")).toBeInTheDocument();
    expect(screen.getByText("Roberto Representante")).toBeInTheDocument();
    expect(screen.getByText("rep@norte.cl")).toBeInTheDocument();

    expect(screen.getByText("pendiente@norte.cl")).toBeInTheDocument();
    expect(screen.getByText("Pendiente")).toBeInTheDocument();
    expect(
      screen.getByLabelText(/correo electrónico del invitado/i),
    ).toBeInTheDocument();
  });

  it("envía una invitación válida y la agrega de inmediato a la tabla de pendientes (CA2)", async () => {
    vi.spyOn(WorkspaceContextModule, "useWorkspace").mockReturnValue(
      baseWorkspaceContext,
    );
    vi.mocked(workspaceService.listWorkspaceMembers).mockResolvedValueOnce([]);
    vi.mocked(workspaceService.listWorkspaceInvitations).mockResolvedValueOnce([]);
    vi.mocked(workspaceService.createInvitation).mockResolvedValueOnce({
      id: "inv-new",
      supplier_id: "sup-1",
      invited_by: "u-admin",
      email: "nuevo@norte.cl",
      role: "member",
      token: "tok-new",
      status: "pending",
      expires_at: "2026-10-01T00:00:00Z",
      created_at: "2026-09-15T12:00:00Z",
    });

    render(
      <CompanyTeamSection
        supplierId="sup-1"
        supplierName="Constructora Norte SpA"
      />,
    );

    const emailInput = await screen.findByLabelText(
      /correo electrónico del invitado/i,
    );
    fireEvent.change(emailInput, { target: { value: "nuevo@norte.cl" } });

    const submitBtn = screen.getByRole("button", {
      name: /enviar invitación/i,
    });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(workspaceService.createInvitation).toHaveBeenCalledWith({
        supplier_id: "sup-1",
        email: "nuevo@norte.cl",
        role: "member",
      });
    });

    expect(await screen.findByText("nuevo@norte.cl")).toBeInTheDocument();
    expect(screen.getByText("Pendiente")).toBeInTheDocument();
    expect(
      screen.getByText(/invitación enviada a nuevo@norte\.cl/i),
    ).toBeInTheDocument();
  });

  it("muestra mensaje de error cuando se intenta invitar un correo duplicado o ya miembro (CA3)", async () => {
    vi.spyOn(WorkspaceContextModule, "useWorkspace").mockReturnValue(
      baseWorkspaceContext,
    );
    vi.mocked(workspaceService.listWorkspaceMembers).mockResolvedValueOnce([]);
    vi.mocked(workspaceService.listWorkspaceInvitations).mockResolvedValueOnce([]);
    vi.mocked(workspaceService.createInvitation).mockRejectedValueOnce(
      new ApiError(
        409,
        "Ya existe una invitación pendiente para este correo electrónico en la organización.",
      ),
    );

    render(
      <CompanyTeamSection
        supplierId="sup-1"
        supplierName="Constructora Norte SpA"
      />,
    );

    const emailInput = await screen.findByLabelText(
      /correo electrónico del invitado/i,
    );
    fireEvent.change(emailInput, { target: { value: "duplicado@norte.cl" } });

    fireEvent.click(
      screen.getByRole("button", { name: /enviar invitación/i }),
    );

    expect(
      await screen.findByText(
        "Ya existe una invitación pendiente para este correo electrónico en la organización.",
      ),
    ).toBeInTheDocument();
  });

  it("permite cancelar una invitación pendiente tras confirmar en el diálogo y la retira de la lista (CA7)", async () => {
    vi.spyOn(WorkspaceContextModule, "useWorkspace").mockReturnValue(
      baseWorkspaceContext,
    );
    vi.mocked(workspaceService.listWorkspaceMembers).mockResolvedValueOnce([]);
    vi.mocked(workspaceService.listWorkspaceInvitations).mockResolvedValueOnce([
      {
        id: "inv-cancel-1",
        supplier_id: "sup-1",
        invited_by: "u-admin",
        email: "revocar@norte.cl",
        role: "member",
        token: "tok-cancel",
        status: "pending",
        expires_at: "2026-10-01T00:00:00Z",
        created_at: "2026-09-10T10:00:00Z",
      },
    ]);
    vi.mocked(workspaceService.cancelInvitation).mockResolvedValueOnce({
      id: "inv-cancel-1",
      supplier_id: "sup-1",
      invited_by: "u-admin",
      email: "revocar@norte.cl",
      role: "member",
      token: "tok-cancel",
      status: "cancelled",
      expires_at: "2026-10-01T00:00:00Z",
      created_at: "2026-09-10T10:00:00Z",
    });

    render(
      <CompanyTeamSection
        supplierId="sup-1"
        supplierName="Constructora Norte SpA"
      />,
    );

    expect(await screen.findByText("revocar@norte.cl")).toBeInTheDocument();

    const cancelBtn = screen.getByRole("button", {
      name: /cancelar invitación de revocar@norte\.cl/i,
    });
    fireEvent.click(cancelBtn);

    const dialog = await screen.findByRole("dialog");
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByText(/revocar@norte\.cl/i)).toBeInTheDocument();

    const confirmBtn = within(dialog).getByRole("button", {
      name: /confirmar cancelación/i,
    });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(workspaceService.cancelInvitation).toHaveBeenCalledWith(
        "inv-cancel-1",
      );
    });

    await waitFor(() => {
      expect(screen.queryByText("revocar@norte.cl")).not.toBeInTheDocument();
    });
    expect(
      screen.getByText(/invitación cancelada correctamente/i),
    ).toBeInTheDocument();
  });
});
