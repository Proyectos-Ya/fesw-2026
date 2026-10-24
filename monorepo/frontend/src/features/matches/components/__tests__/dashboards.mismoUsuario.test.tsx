import React from "react";
import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { HomeDashboard } from "../HomeDashboard";
import { MatchesDashboard } from "../MatchesDashboard";
import * as tenderService from "../../services/tenderService";
import * as savedService from "@/features/saved-tenders/services/savedTenders.service";

// Volver a una pestaña oculta hacía que AuthContext entregara un objeto `user`
// nuevo con el mismo id. Las vistas no deben tomar eso como un cambio de usuario.
let usuarioActual = { id: "user-1", email: "test@example.com" };
const ROUTER = { push: vi.fn(), replace: vi.fn() };
const SIN_PREGUNTAS: never[] = [];

vi.mock("next/navigation", () => ({
  useRouter: () => ROUTER,
}));

vi.mock("@/features/auth/AuthContext", () => ({
  useAuth: () => ({ user: usuarioActual, isLoading: false, isAuthenticated: true }),
}));

vi.mock("../../services/tenderService", () => ({
  getRecommendedTenders: vi.fn(),
}));

vi.mock("@/features/saved-tenders/services/savedTenders.service", () => ({
  fetchSavedTenders: vi.fn(),
  saveTenderApi: vi.fn(),
  unsaveTenderApi: vi.fn(),
}));

vi.mock("../../hooks/useSmartQuestions", () => ({
  useSmartQuestions: () => ({ questions: SIN_PREGUNTAS }),
}));

vi.mock("../../services/questionService", () => ({
  answerSmartQuestion: vi.fn(),
}));

vi.mock("@/features/ranking-telemetry/services/rankingTelemetryService", () => ({
  reportTenderInteraction: vi.fn(),
}));

beforeEach(() => {
  vi.clearAllMocks();
  usuarioActual = { id: "user-1", email: "test@example.com" };
  vi.mocked(tenderService.getRecommendedTenders).mockResolvedValue([]);
  vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([]);
});

describe("dashboards: el mismo usuario en un objeto nuevo no recarga", () => {
  it("HomeDashboard no vuelve a pedir las recomendaciones", async () => {
    const { rerender } = render(<HomeDashboard />);
    await waitFor(() => expect(tenderService.getRecommendedTenders).toHaveBeenCalledTimes(1));

    usuarioActual = { ...usuarioActual };
    rerender(<HomeDashboard />);

    await new Promise((r) => setTimeout(r, 0));
    expect(tenderService.getRecommendedTenders).toHaveBeenCalledTimes(1);
  });

  it("MatchesDashboard no vuelve a pedir los matches ni las guardadas", async () => {
    const { rerender } = render(<MatchesDashboard />);
    await waitFor(() => expect(tenderService.getRecommendedTenders).toHaveBeenCalledTimes(1));
    expect(savedService.fetchSavedTenders).toHaveBeenCalledTimes(1);

    usuarioActual = { ...usuarioActual };
    rerender(<MatchesDashboard />);

    await new Promise((r) => setTimeout(r, 0));
    expect(tenderService.getRecommendedTenders).toHaveBeenCalledTimes(1);
    expect(savedService.fetchSavedTenders).toHaveBeenCalledTimes(1);
  });
});
