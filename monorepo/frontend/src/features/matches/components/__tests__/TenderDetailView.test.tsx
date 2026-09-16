import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TenderDetailView } from "../TenderDetailView";
import * as tenderService from "../../services/tenderService";
import * as savedService from "@/features/saved-tenders/services/savedTenders.service";
import { SAVED_TENDERS_ERRORS } from "@/features/saved-tenders/constants";
import type { DeepAnalysis, MatchingResult, Tender } from "../../tenderTypes";

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
  calculateTenderScore: vi.fn(),
  generateDeepAnalysis: vi.fn(),
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


// ---------------------------------------------------------------------------
// Compatibilidad a pedido: nada se calcula por abrir la ficha
// ---------------------------------------------------------------------------

/** Abierta de verdad: la ficha esconde los botones de una licitación vencida. */
const EN_UN_MES = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString();

const tenderFueraDelTop: Tender = {
  ...(mockMatch.tender as Tender),
  id: "tender-77",
  name: "Mantención de ascensores",
  closing_at: EN_UN_MES,
};

const analisisGuardado: DeepAnalysis = {
  id: "ana-1",
  tender_id: "tender-77",
  supplier_id: "sup-1",
  compatibility_score: 64,
  recommendation: "Evaluar con cautela",
  justification: "Escrita con el perfil anterior.",
  prompt_instruction: null,
  created_at: "2026-06-01T00:00:00Z",
  updated_at: "2026-06-01T00:00:00Z",
};

describe("TenderDetailView: compatibilidad a pedido", () => {
  const user = userEvent.setup();

  beforeEach(() => {
    vi.clearAllMocks();
    // Fuera de las recomendadas: la ficha cae al detalle directo.
    vi.mocked(tenderService.getRecommendedTenders).mockResolvedValue([]);
    vi.mocked(tenderService.getDeepAnalysisOnly).mockResolvedValue(null as never);
    vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([]);
    vi.mocked(tenderService.getTenderDetail).mockResolvedValue({
      tender: tenderFueraDelTop,
      score_pct: null,
      is_closed: false,
    });
  });

  it("muestra 'Sin puntaje' y no calcula nada al abrir la ficha", async () => {
    render(<TenderDetailView tenderId="tender-77" />);

    expect(await screen.findByText("Sin puntaje")).toBeInTheDocument();
    // Un 0% diría "no calzas"; lo cierto es que nadie lo midió.
    expect(
      screen.queryByRole("img", { name: "Compatibilidad 0%" })
    ).not.toBeInTheDocument();
    expect(tenderService.calculateTenderScore).not.toHaveBeenCalled();
    expect(tenderService.generateDeepAnalysis).not.toHaveBeenCalled();
  });

  it("calcula la compatibilidad cuando el usuario lo pide", async () => {
    vi.mocked(tenderService.calculateTenderScore).mockResolvedValue({
      score_pct: 73,
      calculated_at: "2026-09-16T10:00:00Z",
    });

    render(<TenderDetailView tenderId="tender-77" />);

    await user.click(await screen.findByRole("button", { name: /calcular compatibilidad/i }));

    expect(tenderService.calculateTenderScore).toHaveBeenCalledWith("tender-77");
    // El medidor parte el número del signo, así que se busca por su etiqueta.
    expect(
      await screen.findByRole("img", { name: "Compatibilidad 73%" })
    ).toBeInTheDocument();
    expect(screen.queryByText("Sin puntaje")).not.toBeInTheDocument();
  });

  it("ofrece recalcular cuando la licitación ya tiene puntaje", async () => {
    vi.mocked(tenderService.getTenderDetail).mockResolvedValue({
      tender: tenderFueraDelTop,
      score_pct: 40,
      is_closed: false,
    });

    render(<TenderDetailView tenderId="tender-77" />);

    expect(await screen.findByRole("button", { name: /recalcular/i })).toBeInTheDocument();
  });

  it("avisa que el análisis quedó desactualizado y permite actualizarlo", async () => {
    vi.mocked(tenderService.getDeepAnalysisOnly).mockResolvedValue({
      ...analisisGuardado,
      is_outdated: true,
    });
    vi.mocked(tenderService.generateDeepAnalysis).mockResolvedValue({
      ...analisisGuardado,
      compatibility_score: 81,
      is_outdated: false,
    });

    render(<TenderDetailView tenderId="tender-77" />);

    expect(
      await screen.findByText("Este análisis está desactualizado")
    ).toBeInTheDocument();
    // Abrir la ficha no regenera: la llamada llega solo con el clic.
    expect(tenderService.generateDeepAnalysis).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: /actualizar análisis/i }));

    expect(tenderService.generateDeepAnalysis).toHaveBeenCalledWith(
      "tender-77",
      undefined,
      true
    );
    // El puntaje se actualiza en el medidor de la ficha y en la tarjeta del
    // análisis: los dos salen del mismo número.
    await waitFor(() => {
      expect(
        screen.getAllByRole("img", { name: "Compatibilidad 81%" })
      ).toHaveLength(2);
    });
  });

  it("no ofrece calcular ni generar en una licitación cerrada", async () => {
    vi.mocked(tenderService.getTenderDetail).mockResolvedValue({
      tender: tenderFueraDelTop,
      score_pct: null,
      is_closed: true,
    });

    render(<TenderDetailView tenderId="tender-77" />);

    await waitFor(() => {
      expect(screen.getByText("Esta licitación ya cerró")).toBeInTheDocument();
    });
    expect(
      screen.queryByRole("button", { name: /calcular compatibilidad/i })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /análisis de compatibilidad ia/i })
    ).not.toBeInTheDocument();
  });
});

describe("TenderDetailView: puntaje de una recomendada", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([]);
    vi.mocked(tenderService.getDeepAnalysisOnly).mockResolvedValue(null as never);
    vi.mocked(tenderService.getRecommendedTenders).mockResolvedValue([
      {
        ...mockMatch,
        tender: { ...(mockMatch.tender as Tender), closing_at: EN_UN_MES },
        final_score: 0.91,
      },
    ]);
  });

  it("no ofrece recalcular: ese puntaje lo mantiene el ranking", async () => {
    render(<TenderDetailView tenderId="tender-50" />);

    expect(
      await screen.findByRole("img", { name: "Compatibilidad 91%" })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /recalcular/i })
    ).not.toBeInTheDocument();
    expect(tenderService.getTenderDetail).not.toHaveBeenCalled();
  });
});
