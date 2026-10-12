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

  it("no muestra el banner de invitaciones en el dashboard de recomendaciones para no saturar al usuario con empresa activa", async () => {
    vi.mocked(tenderService.getRecommendedTenders).mockResolvedValue([]);

    vi.spyOn(WorkspaceContextModule, "useWorkspace").mockReturnValue({
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
      acceptPendingInvitation: vi.fn(),
      rejectPendingInvitation: vi.fn(),
    });

    render(<HomeDashboard />);

    expect(
      await screen.findByText("Sin licitaciones de alta compatibilidad hoy"),
    ).toBeInTheDocument();

    // El dashboard de licitaciones no debe tener el banner invasivo
    expect(screen.queryByText(/Ingeniería Austral SpA/)).not.toBeInTheDocument();
    expect(
      screen.queryByText(/sin perder tus membresías actuales/i),
    ).not.toBeInTheDocument();
  });
});
