import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ApiError } from "@/features/shared/api/client";
import { WorkspaceProvider, useWorkspace } from "../WorkspaceContext";
import * as workspaceService from "../services/workspaceService";

vi.mock("@/features/auth/AuthContext", () => ({
  useAuth: () => ({
    user: { id: "u-1", email: "user@test.cl", full_name: "Usuario Test" },
    isAuthenticated: true,
  }),
}));

vi.mock("../services/workspaceService", () => ({
  listWorkspaces: vi.fn(),
  getCurrentWorkspace: vi.fn(),
  getMyInvitations: vi.fn(),
  acceptInvitation: vi.fn(),
  rejectInvitation: vi.fn(),
  switchWorkspace: vi.fn(),
  clearActiveWorkspace: vi.fn(),
}));

function TestConsumer() {
  const {
    workspaces,
    activeWorkspace,
    invitations,
    acceptPendingInvitation,
    rejectPendingInvitation,
  } = useWorkspace();

  return (
    <div>
      <span data-testid="ws-count">{workspaces.length}</span>
      <span data-testid="active-ws">{activeWorkspace?.active_supplier_name ?? "none"}</span>
      <span data-testid="inv-count">{invitations.length}</span>
      <button
        type="button"
        onClick={() => void acceptPendingInvitation("tok-accept")}
      >
        Aceptar
      </button>
      <button
        type="button"
        onClick={() => void rejectPendingInvitation("tok-reject")}
      >
        Rechazar
      </button>
    </div>
  );
}

describe("WorkspaceContext", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("acceptPendingInvitation acepta la invitación y refresca workspaces e invitaciones (CA6)", async () => {
    vi.mocked(workspaceService.listWorkspaces)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([
        {
          supplier_id: "s-new",
          legal_name: "Constructora Austral SpA",
          trade_name: "Austral",
          rut: "76.123.456-0",
          role: "member",
          status: "active",
          is_active_context: true,
        },
      ]);
    vi.mocked(workspaceService.getCurrentWorkspace)
      .mockRejectedValueOnce(new Error("Sin workspace"))
      .mockResolvedValueOnce({
        user_id: "u-1",
        active_supplier_id: "s-new",
        active_supplier_name: "Austral",
        role: "member",
        permissions: ["view_matches"],
        is_admin: false,
      });
    vi.mocked(workspaceService.getMyInvitations)
      .mockResolvedValueOnce([
        {
          id: "inv-1",
          supplier_id: "s-new",
          supplier_name: "Austral",
          invited_by: "u-admin",
          email: "user@test.cl",
          role: "member",
          token: "tok-accept",
          status: "pending",
          expires_at: "2026-10-01T00:00:00Z",
          created_at: "2026-09-12T00:00:00Z",
        },
      ])
      .mockResolvedValueOnce([]);
    vi.mocked(workspaceService.acceptInvitation).mockResolvedValueOnce({
      id: "m-1",
      user_id: "u-1",
      supplier_id: "s-new",
      role: "member",
    });

    render(
      <WorkspaceProvider>
        <TestConsumer />
      </WorkspaceProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("inv-count")).toHaveTextContent("1");
    });

    fireEvent.click(screen.getByRole("button", { name: "Aceptar" }));

    await waitFor(() => {
      expect(workspaceService.acceptInvitation).toHaveBeenCalledWith({
        token: "tok-accept",
      });
      expect(screen.getByTestId("inv-count")).toHaveTextContent("0");
      expect(screen.getByTestId("ws-count")).toHaveTextContent("1");
      expect(screen.getByTestId("active-ws")).toHaveTextContent("Austral");
    });
  });

  it("rejectPendingInvitation rechaza la invitación y refresca invitaciones (CA4)", async () => {
    vi.mocked(workspaceService.listWorkspaces).mockResolvedValue([]);
    vi.mocked(workspaceService.getCurrentWorkspace).mockRejectedValue(
      new Error("Sin workspace"),
    );
    vi.mocked(workspaceService.getMyInvitations)
      .mockResolvedValueOnce([
        {
          id: "inv-2",
          supplier_id: "s-new",
          supplier_name: "Austral",
          invited_by: "u-admin",
          email: "user@test.cl",
          role: "member",
          token: "tok-reject",
          status: "pending",
          expires_at: "2026-10-01T00:00:00Z",
          created_at: "2026-09-12T00:00:00Z",
        },
      ])
      .mockResolvedValueOnce([]);
    vi.mocked(workspaceService.rejectInvitation).mockResolvedValueOnce({
      id: "inv-2",
      supplier_id: "s-new",
      invited_by: "u-admin",
      email: "user@test.cl",
      role: "member",
      token: "tok-reject",
      status: "rejected",
      expires_at: "2026-10-01T00:00:00Z",
      created_at: "2026-09-12T00:00:00Z",
    });

    render(
      <WorkspaceProvider>
        <TestConsumer />
      </WorkspaceProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("inv-count")).toHaveTextContent("1");
    });

    fireEvent.click(screen.getByRole("button", { name: "Rechazar" }));

    await waitFor(() => {
      expect(workspaceService.rejectInvitation).toHaveBeenCalledWith({
        token: "tok-reject",
      });
      expect(screen.getByTestId("inv-count")).toHaveTextContent("0");
    });
  });

  it("muestra modal de bloqueo en caliente ante error 403 por revocación y permite volver al inicio (HU-13 CA3)", async () => {
    vi.mocked(workspaceService.listWorkspaces).mockResolvedValue([]);
    vi.mocked(workspaceService.getMyInvitations).mockResolvedValue([]);
    vi.mocked(workspaceService.getCurrentWorkspace).mockRejectedValueOnce(
      new ApiError(403, "Tu acceso a este espacio de trabajo ha sido revocado."),
    );
    vi.mocked(workspaceService.clearActiveWorkspace).mockResolvedValueOnce(
      undefined,
    );

    render(
      <WorkspaceProvider>
        <TestConsumer />
      </WorkspaceProvider>,
    );

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
      expect(
        screen.getByText(/Tu acceso a este espacio de trabajo ha sido revocado/i),
      ).toBeInTheDocument();
    });

    const goHomeButton = screen.getByRole("button", { name: /Ir al inicio/i });
    fireEvent.click(goHomeButton);

    await waitFor(() => {
      expect(workspaceService.clearActiveWorkspace).toHaveBeenCalledTimes(1);
    });
  });

  it("revalida invitaciones al enfocar la ventana (window focus)", async () => {
    vi.mocked(workspaceService.listWorkspaces).mockResolvedValue([]);
    vi.mocked(workspaceService.getCurrentWorkspace).mockResolvedValue({
      user_id: "u-1",
      active_supplier_id: "s-1",
      active_supplier_name: "Empresa 1",
      role: "admin",
      permissions: [],
      is_admin: true,
    });
    vi.mocked(workspaceService.getMyInvitations).mockResolvedValue([]);

    render(
      <WorkspaceProvider>
        <TestConsumer />
      </WorkspaceProvider>,
    );

    await waitFor(() => {
      expect(workspaceService.getMyInvitations).toHaveBeenCalledTimes(1);
    });

    // Disparar evento de foco en la ventana
    fireEvent.focus(window);

    await waitFor(() => {
      expect(workspaceService.getMyInvitations).toHaveBeenCalledTimes(2);
    });
  });
});
