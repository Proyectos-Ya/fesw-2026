import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MatchesDashboard } from "../MatchesDashboard";
import * as tenderService from "../../services/tenderService";
import * as savedService from "@/features/saved-tenders/services/savedTenders.service";
import { SAVED_TENDERS_ERRORS } from "@/features/saved-tenders/constants";
import type { MatchingResult } from "../../tenderTypes";

const mockRouter = {
  push: vi.fn(),
  replace: vi.fn(),
};

const mockUser = { id: "user-1", email: "test@example.com" };

vi.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
}));

vi.mock("@/features/auth/AuthContext", () => ({
  useAuth: () => ({
    user: mockUser,
    isLoading: false,
    isAuthenticated: true,
  }),
}));

vi.mock("../../services/tenderService", () => ({
  getRecommendedTenders: vi.fn(),
}));

vi.mock("@/features/saved-tenders/services/savedTenders.service", () => ({
  fetchSavedTenders: vi.fn(),
  saveTenderApi: vi.fn(),
  unsaveTenderApi: vi.fn(),
}));

const mockMatch: MatchingResult = {
  id: "match-1",
  supplier_id: "sup-1",
  tender_id: "tender-1",
  similarity_score: 90,
  reranker_score: 90,
  final_score: 90,
  model_version: "v1",
  calculated_at: "2026-06-01T00:00:00Z",
  tender: {
    id: "tender-1",
    code: "111-22-COT26",
    name: "Licitación de Hardware",
    description: "Equipamiento computacional",
    status_id: 1,
    status_code: "publicada",
    published_at: "2026-06-01T00:00:00Z",
    closing_at: "2026-06-25T00:00:00Z",
    last_change_at: "2026-06-01T00:00:00Z",
    buyer_rut: "111-1",
    buyer_name: "Subsecretaría",
    buyer_unit: "Informática",
    region: "Metropolitana",
    province: "Santiago",
    commune: "Santiago",
    available_amount_clp: 15000000,
    created_at: "2026-06-01T00:00:00Z",
    updated_at: "2026-06-01T00:00:00Z",
    items: [],
  },
};

describe("MatchesDashboard (CA-5: Rollback y notificación en error de red)", () => {
  const user = userEvent.setup();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(tenderService.getRecommendedTenders).mockResolvedValue([mockMatch]);
  });

  it("aplica rollback al estado previo y muestra notificación cuando falla guardar por error de red", async () => {
    vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([]);
    vi.mocked(savedService.saveTenderApi).mockRejectedValue(
      new TypeError("Failed to fetch"),
    );

    render(<MatchesDashboard />);

    await waitFor(() => {
      expect(screen.getByText("Licitación de Hardware")).toBeInTheDocument();
    });

    const saveButton = screen.getByRole("button", { name: "Guardar licitación" });
    await user.click(saveButton);

    // Alerta visible con el mensaje correspondiente
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(SAVED_TENDERS_ERRORS.SAVE_FAILED);
    expect(alert).toHaveTextContent(
      /la operación no pudo realizarse y se mantuvo el estado anterior/i,
    );

    // El botón vuelve al estado anterior (no guardada)
    expect(screen.getByRole("button", { name: "Guardar licitación" })).toBeInTheDocument();
  });

  it("aplica rollback al estado previo y muestra notificación cuando falla quitar de guardados", async () => {
    vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([mockMatch]);
    vi.mocked(savedService.unsaveTenderApi).mockRejectedValue(
      new TypeError("Failed to fetch"),
    );

    render(<MatchesDashboard />);

    await waitFor(() => {
      expect(screen.getByText("Licitación de Hardware")).toBeInTheDocument();
    });

    const unsaveButton = screen.getByRole("button", {
      name: "Quitar de licitaciones guardadas",
    });
    await user.click(unsaveButton);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(SAVED_TENDERS_ERRORS.UNSAVE_FAILED);

    // El botón vuelve al estado anterior (guardada)
    expect(
      screen.getByRole("button", { name: "Quitar de licitaciones guardadas" }),
    ).toBeInTheDocument();
  });
});
