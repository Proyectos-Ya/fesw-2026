import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ApiError } from "@/features/shared/api/client";
import { HomeDashboard } from "../HomeDashboard";
import * as WorkspaceContextModule from "@/features/workspaces/WorkspaceContext";
import * as tenderService from "../../services/tenderService";
import type { SupplierInvitation } from "@/features/workspaces/types";

const STABLE_ROUTER = {
  replace: vi.fn(),
  push: vi.fn(),
};

vi.mock("next/navigation", () => ({
  useRouter: () => STABLE_ROUTER,
}));

const STABLE_USER = {
  id: "u-1",
  email: "invitado@empresa.cl",
  full_name: "Invitado",
};

vi.mock("@/features/auth/AuthContext", () => ({
  useAuth: () => ({
    user: STABLE_USER,
    isLoading: false,
    isAuthenticated: true,
  }),
}));

vi.mock("../../services/tenderService", () => ({
  getRecommendedTenders: vi.fn(),
}));

const EMPTY_QUESTIONS: never[] = [];

vi.mock("../../hooks/useSmartQuestions", () => ({
  useSmartQuestions: () => ({ questions: EMPTY_QUESTIONS }),
}));

vi.mock("../../services/questionService", () => ({
  answerSmartQuestion: vi.fn(),
}));

const pendingInvitation: SupplierInvitation = {
  id: "inv-home-1",
  supplier_id: "sup-austral",
  supplier_name: "Ingeniería Austral SpA",
  supplier_rut: "76.123.456-0",
  invited_by: "u-admin",
  email: "invitado@empresa.cl",
  role: "member",
  token: "tok-home-1",
  status: "pending",
  expires_at: "2026-10-01T00:00:00Z",
  created_at: "2026-09-15T10:00:00Z",
};

describe("HomeDashboard - Banner de invitaciones pendientes (CA4, CA5, CA6)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("muestra el banner de invitación pendiente en la pantalla de crear empresa para usuario sin organización (CA4)", async () => {
    vi.mocked(tenderService.getRecommendedTenders).mockRejectedValueOnce(
      new ApiError(404, "Sin empresa"),
    );

    vi.spyOn(WorkspaceContextModule, "useWorkspace").mockReturnValue({
      workspaces: [],
      recentWorkspaces: [],
      activeWorkspace: null,
      invitations: [pendingInvitation],
      isLoading: false,
      isAdmin: false,
      hasPermission: () => false,
      switchActiveWorkspace: vi.fn(),
      refreshWorkspaces: vi.fn(),
      refreshInvitations: vi.fn(),
      acceptPendingInvitation: vi.fn(),
      rejectPendingInvitation: vi.fn(),
    });

    render(<HomeDashboard />);

    expect(
      await screen.findByText("Primero crea tu perfil inteligente"),
    ).toBeInTheDocument();
    expect(screen.getByText(/Ingeniería Austral SpA/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /aceptar invitación/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /rechazar/i }),
    ).toBeInTheDocument();
  });

  it("muestra el banner sobre las recomendaciones para usuario con organizaciones previas e informa que conserva sus membresías (CA5, CA6)", async () => {
    vi.mocked(tenderService.getRecommendedTenders).mockResolvedValue([]);
    const mockAccept = vi.fn().mockResolvedValue(undefined);

    const spy = vi.spyOn(WorkspaceContextModule, "useWorkspace").mockReturnValue({
      workspaces: [
        {
          supplier_id: "sup-prev",
          legal_name: "Consultora Andina Ltda",
          trade_name: "Andina",
          rut: "77.654.321-7",
          role: "admin",
          status: "active",
          is_active_context: true,
        },
      ],
      recentWorkspaces: [],
      activeWorkspace: {
        user_id: "u-1",
        active_supplier_id: "sup-prev",
        active_supplier_name: "Andina",
        role: "admin",
        permissions: ["invite_members"],
        is_admin: true,
      },
      invitations: [pendingInvitation],
      isLoading: false,
      isAdmin: true,
      hasPermission: () => true,
      switchActiveWorkspace: vi.fn(),
      refreshWorkspaces: vi.fn(),
      refreshInvitations: vi.fn(),
      acceptPendingInvitation: mockAccept,
      rejectPendingInvitation: vi.fn(),
    });

    const { rerender } = render(<HomeDashboard />);

    expect(
      await screen.findByText("Sin licitaciones de alta compatibilidad hoy"),
    ).toBeInTheDocument();
    expect(screen.getByText(/Ingeniería Austral SpA/)).toBeInTheDocument();
    expect(
      screen.getByText(/sin perder tus membresías actuales/i),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /aceptar invitación/i }));

    await waitFor(() => {
      expect(mockAccept).toHaveBeenCalledWith("tok-home-1");
    });

    // Tras aceptar, las invitaciones quedan vacías y el banner desaparece (CA6)
    spy.mockReturnValue({
      workspaces: [
        {
          supplier_id: "sup-prev",
          legal_name: "Consultora Andina Ltda",
          trade_name: "Andina",
          rut: "77.654.321-7",
          role: "admin",
          status: "active",
          is_active_context: true,
        },
        {
          supplier_id: "sup-austral",
          legal_name: "Ingeniería Austral SpA",
          trade_name: "Austral",
          rut: "76.123.456-0",
          role: "member",
          status: "active",
          is_active_context: false,
        },
      ],
      recentWorkspaces: [],
      activeWorkspace: {
        user_id: "u-1",
        active_supplier_id: "sup-prev",
        active_supplier_name: "Andina",
        role: "admin",
        permissions: ["invite_members"],
        is_admin: true,
      },
      invitations: [],
      isLoading: false,
      isAdmin: true,
      hasPermission: () => true,
      switchActiveWorkspace: vi.fn(),
      refreshWorkspaces: vi.fn(),
      refreshInvitations: vi.fn(),
      acceptPendingInvitation: mockAccept,
      rejectPendingInvitation: vi.fn(),
    });

    rerender(<HomeDashboard />);

    await waitFor(() => {
      expect(
        screen.queryByText(/Ingeniería Austral SpA/),
      ).not.toBeInTheDocument();
      expect(
        screen.getByText("Sin licitaciones de alta compatibilidad hoy"),
      ).toBeInTheDocument();
    });
  });
});
