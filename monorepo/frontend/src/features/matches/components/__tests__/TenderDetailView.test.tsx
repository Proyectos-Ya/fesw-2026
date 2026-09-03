import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TenderDetailView } from "../TenderDetailView";
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
  getDeepAnalysisOnly: vi.fn(),
  getTenderDetail: vi.fn(),
}));

vi.mock("@/features/tender-assistant/components/TenderAssistantDrawer", () => ({
  TenderAssistantDrawer: () => null,
}));

vi.mock("@/features/saved-tenders/services/savedTenders.service", () => ({
  fetchSavedTenders: vi.fn(),
  saveTenderApi: vi.fn(),
  unsaveTenderApi: vi.fn(),
}));

const mockMatch: MatchingResult = {
  id: "match-50",
  supplier_id: "sup-1",
  tender_id: "tender-50",
  similarity_score: 95,
  reranker_score: 95,
  final_score: 95,
  model_version: "v1",
  calculated_at: "2026-06-01T00:00:00Z",
  tender: {
    id: "tender-50",
    code: "555-66-COT26",
    name: "Servicios de Seguridad y Redes",
    description: "Ciberseguridad integral",
    status_id: 1,
    status_code: "publicada",
    published_at: "2026-06-01T00:00:00Z",
    closing_at: "2026-06-30T00:00:00Z",
    last_change_at: "2026-06-01T00:00:00Z",
    buyer_rut: "111-1",
    buyer_name: "Ministerio de Hacienda",
    buyer_unit: "Seguridad",
    region: "Metropolitana",
    province: "Santiago",
    commune: "Santiago",
    available_amount_clp: 20000000,
    created_at: "2026-06-01T00:00:00Z",
    updated_at: "2026-06-01T00:00:00Z",
    items: [],
  },
};

describe("TenderDetailView (CA-5: Rollback y notificación en error de red)", () => {
  const user = userEvent.setup();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(tenderService.getRecommendedTenders).mockResolvedValue([mockMatch]);
    vi.mocked(tenderService.getDeepAnalysisOnly).mockResolvedValue(null as never);
  });

  it("aplica rollback al estado previo y muestra alerta ante fallo al guardar licitación", async () => {
    vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([]);
    vi.mocked(savedService.saveTenderApi).mockRejectedValue(
      new TypeError("Failed to fetch"),
    );

    render(<TenderDetailView tenderId="tender-50" />);

    await waitFor(() => {
      expect(screen.getByText("Servicios de Seguridad y Redes")).toBeInTheDocument();
    });

    const saveButton = screen.getByRole("button", { name: "Guardar licitación" });
    await user.click(saveButton);

    const alert = await screen.findByText(SAVED_TENDERS_ERRORS.SAVE_FAILED);
    expect(alert).toBeInTheDocument();
    expect(alert).toHaveTextContent(
      /la operación no pudo realizarse y se mantuvo el estado anterior/i,
    );

    // Rollback: el botón vuelve a estar desmarcado
    expect(screen.getByRole("button", { name: "Guardar licitación" })).toBeInTheDocument();
  });

  it("aplica rollback al estado previo y muestra alerta ante fallo al quitar licitación guardada", async () => {
    vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([mockMatch]);
    vi.mocked(savedService.unsaveTenderApi).mockRejectedValue(
      new TypeError("Failed to fetch"),
    );

    render(<TenderDetailView tenderId="tender-50" />);

    await waitFor(() => {
      expect(screen.getByText("Servicios de Seguridad y Redes")).toBeInTheDocument();
    });

    const unsaveButton = screen.getByRole("button", {
      name: "Quitar de licitaciones guardadas",
    });
    await user.click(unsaveButton);

    const alert = await screen.findByText(SAVED_TENDERS_ERRORS.UNSAVE_FAILED);
    expect(alert).toBeInTheDocument();

    // Rollback: el botón vuelve a estar marcado como guardado
    expect(
      screen.getByRole("button", { name: "Quitar de licitaciones guardadas" }),
    ).toBeInTheDocument();
  });
});
