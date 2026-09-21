import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TenderAnalysisView } from "../TenderAnalysisView";
import * as tenderService from "../../services/tenderService";
import { ApiError } from "@/features/shared/api/client";
import type { DeepAnalysis, Tender } from "../../tenderTypes";

const mockRouter = { push: vi.fn(), replace: vi.fn(), back: vi.fn() };
// Referencia estable: el efecto de carga depende de la identidad de `user`, y
// un objeto nuevo por render lo dispararía en bucle.
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
  getTenderDetail: vi.fn(),
  getDeepAnalysis: vi.fn(),
  getDeepAnalysisOnly: vi.fn(),
  generateDeepAnalysis: vi.fn(),
}));

const EN_UN_MES = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString();

/** Una licitación cualquiera: la idea es justamente que no sea un match. */
const tender: Tender = {
  id: "tender-99",
  code: "777-88-COT26",
  name: "Reparación de luminarias",
  description: "Mantención de alumbrado público",
  status_id: 1,
  status_code: "publicada",
  published_at: "2026-09-01T00:00:00Z",
  closing_at: EN_UN_MES,
  last_change_at: "2026-09-01T00:00:00Z",
  buyer_rut: "999-9",
  buyer_name: "Municipalidad de Valparaíso",
  buyer_unit: "Obras",
  region: "Valparaíso",
  province: "Valparaíso",
  commune: "Valparaíso",
  available_amount_clp: 4000000,
  created_at: "2026-09-01T00:00:00Z",
  updated_at: "2026-09-01T00:00:00Z",
  items: [],
};

const analisis: DeepAnalysis = {
  id: "ana-99",
  tender_id: "tender-99",
  supplier_id: "sup-1",
  compatibility_score: 68,
  recommendation: "Evaluar con cautela",
  justification: "Cumple lo principal, con reparos en plazos.",
  prompt_instruction: null,
  created_at: "2026-09-10T00:00:00Z",
  updated_at: "2026-09-10T00:00:00Z",
};

describe("TenderAnalysisView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(tenderService.getTenderDetail).mockResolvedValue({
      tender,
      score_pct: null,
      is_closed: false,
    });
    vi.mocked(tenderService.getDeepAnalysis).mockResolvedValue(analisis);
    vi.mocked(tenderService.getDeepAnalysisOnly).mockResolvedValue(analisis);
  });

  it("analiza una licitación que no está entre las recomendadas", async () => {
    render(<TenderAnalysisView tenderId="tender-99" />);

    expect(
      await screen.findByText(/Análisis de compatibilidad IA: Reparación de luminarias/)
    ).toBeInTheDocument();
    expect(
      await screen.findByText("Cumple lo principal, con reparos en plazos.")
    ).toBeInTheDocument();
    expect(tenderService.getDeepAnalysis).toHaveBeenCalledWith("tender-99");
  });

  it("muestra 'no encontramos' solo si la licitación no existe", async () => {
    vi.mocked(tenderService.getTenderDetail).mockRejectedValue(
      new ApiError(404, "No existe")
    );

    render(<TenderAnalysisView tenderId="tender-99" />);

    expect(
      await screen.findByText("No encontramos esta licitación")
    ).toBeInTheDocument();
    expect(tenderService.getDeepAnalysis).not.toHaveBeenCalled();
  });

  it("en una licitación cerrada muestra el análisis previo sin generar nada", async () => {
    vi.mocked(tenderService.getTenderDetail).mockResolvedValue({
      tender,
      score_pct: 68,
      is_closed: true,
    });

    render(<TenderAnalysisView tenderId="tender-99" />);

    expect(
      await screen.findByText("Cumple lo principal, con reparos en plazos.")
    ).toBeInTheDocument();
    expect(tenderService.getDeepAnalysisOnly).toHaveBeenCalledWith("tender-99");
    expect(tenderService.getDeepAnalysis).not.toHaveBeenCalled();
    // Sin plazo que cumplir, regenerar no ayuda a decidir nada.
    expect(
      screen.queryByRole("button", { name: /regenerar análisis/i })
    ).not.toBeInTheDocument();
  });

  it("avisa cuando una licitación cerrada nunca tuvo análisis", async () => {
    vi.mocked(tenderService.getTenderDetail).mockResolvedValue({
      tender,
      score_pct: null,
      is_closed: true,
    });
    vi.mocked(tenderService.getDeepAnalysisOnly).mockResolvedValue(null);

    render(<TenderAnalysisView tenderId="tender-99" />);

    await waitFor(() => {
      expect(
        screen.getByText(/cerró sin que se generara un análisis/i)
      ).toBeInTheDocument();
    });
    expect(tenderService.getDeepAnalysis).not.toHaveBeenCalled();
  });
});
