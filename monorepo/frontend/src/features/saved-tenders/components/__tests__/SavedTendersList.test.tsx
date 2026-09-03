import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SavedTendersList } from "../SavedTendersList";
import * as savedService from "../../services/savedTenders.service";
import { SAVED_TENDERS_ERRORS } from "../../constants";
import { ApiError } from "@/features/shared/api/client";
import type { MatchingResult } from "@/features/matches/tenderTypes";

vi.mock("@/features/auth/AuthContext", () => ({
  useAuth: () => ({
    user: { id: "user-1", email: "test@example.com" },
    isLoading: false,
    isAuthenticated: true,
  }),
}));

vi.mock("../../services/savedTenders.service", () => ({
  fetchSavedTenders: vi.fn(),
  unsaveTenderApi: vi.fn(),
  saveTenderApi: vi.fn(),
}));

const mockSavedMatch: MatchingResult = {
  id: "match-100",
  supplier_id: "sup-1",
  tender_id: "tender-100",
  similarity_score: 90,
  reranker_score: 95,
  final_score: 92,
  model_version: "v1",
  calculated_at: "2026-06-01T00:00:00Z",
  tender: {
    id: "tender-100",
    code: "777-88-COT26",
    name: "Servicio de Consultoría TI",
    description: "Consultoría estratégica",
    status_id: 1,
    status_code: "publicada",
    published_at: "2026-06-01T00:00:00Z",
    closing_at: "2026-06-20T00:00:00Z",
    last_change_at: "2026-06-01T00:00:00Z",
    buyer_rut: "999-9",
    buyer_name: "Ministerio de Salud",
    buyer_unit: "División TI",
    region: "Metropolitana",
    province: "Santiago",
    commune: "Santiago",
    available_amount_clp: 5000000,
    created_at: "2026-06-01T00:00:00Z",
    updated_at: "2026-06-01T00:00:00Z",
    items: [],
    is_saved: true,
  },
};

describe("SavedTendersList (CA-5: Rollback y notificación en error de red)", () => {
  const user = userEvent.setup();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renderiza la lista de licitaciones guardadas correctamente", async () => {
    vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([mockSavedMatch]);

    render(<SavedTendersList />);

    await waitFor(() => {
      expect(screen.getByText("Servicio de Consultoría TI")).toBeInTheDocument();
    });

    expect(
      screen.getByText("Tienes 1 licitación guardada para seguimiento."),
    ).toBeInTheDocument();
  });

  it("aplica rollback restaurando la tarjeta y notifica error visible ante fallo de conexión de red", async () => {
    vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([mockSavedMatch]);
    vi.mocked(savedService.unsaveTenderApi).mockRejectedValue(
      new TypeError("Failed to fetch"),
    );

    render(<SavedTendersList />);

    await waitFor(() => {
      expect(screen.getByText("Servicio de Consultoría TI")).toBeInTheDocument();
    });

    const unsaveButton = screen.getByRole("button", {
      name: /quitar de licitaciones guardadas/i,
    });

    await user.click(unsaveButton);

    // Debe mostrarse la alerta visible con el mensaje correspondiente a CA-5
    const alert = await screen.findByRole("alert");
    expect(alert).toBeInTheDocument();
    expect(alert).toHaveTextContent(SAVED_TENDERS_ERRORS.UNSAVE_FAILED);
    expect(alert).toHaveTextContent(
      /la operación no pudo realizarse y se mantuvo el estado anterior/i,
    );

    // El estado previo de la tarjeta se mantiene en la interfaz (rollback)
    expect(screen.getByText("Servicio de Consultoría TI")).toBeInTheDocument();

    // Permite cerrar el banner de alerta
    const closeBtn = screen.getByRole("button", { name: /cerrar/i });
    await user.click(closeBtn);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("aplica rollback restaurando la tarjeta y notifica error visible ante error HTTP 500", async () => {
    vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([mockSavedMatch]);
    vi.mocked(savedService.unsaveTenderApi).mockRejectedValue(
      new ApiError(500, "Internal Server Error"),
    );

    render(<SavedTendersList />);

    await waitFor(() => {
      expect(screen.getByText("Servicio de Consultoría TI")).toBeInTheDocument();
    });

    const unsaveButton = screen.getByRole("button", {
      name: /quitar de licitaciones guardadas/i,
    });

    await user.click(unsaveButton);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(SAVED_TENDERS_ERRORS.UNSAVE_FAILED);

    // Rollback verificado: la tarjeta no se eliminó
    expect(screen.getByText("Servicio de Consultoría TI")).toBeInTheDocument();
  });
});
