import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TenderDetailView } from "../TenderDetailView";
import * as tenderService from "../../services/tenderService";
import * as savedService from "@/features/saved-tenders/services/savedTenders.service";
import { reportTenderInteraction } from "@/features/ranking-telemetry/services/rankingTelemetryService";
import type { RankingContext } from "@/features/ranking-telemetry/types";
import type { MatchingResult, Tender } from "../../tenderTypes";

const RK = "0b6f3d2e-8f1a-4c53-9a6e-2d1c7b9e4a10";
const CTX: RankingContext = { rankingId: RK, position: 2 };

const mockRouter = { push: vi.fn(), replace: vi.fn(), back: vi.fn() };
const mockUser = { id: "user-1", email: "test@example.com" };

vi.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
}));

vi.mock("@/features/auth/AuthContext", () => ({
  useAuth: () => ({ user: mockUser, isLoading: false, isAuthenticated: true }),
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

vi.mock("@/features/tender-milestones/components/MilestonesSection", () => ({
  MilestonesSection: () => null,
}));

vi.mock("@/features/tender-attachments/components/TenderAttachmentsPanel", () => ({
  TenderAttachmentsPanel: ({ onUploadSuccess }: { onUploadSuccess?: () => void }) => (
    <button onClick={() => onUploadSuccess?.()}>Simular subida de anexo</button>
  ),
}));

vi.mock("@/features/tender-attachments/components/DigestCard", () => ({
  DigestCard: () => null,
}));

vi.mock("@/features/quotations/QuotationEditor", () => ({
  QuotationEditor: ({ onSaved }: { onSaved?: () => void }) => (
    <button onClick={() => onSaved?.()}>Simular cotización guardada</button>
  ),
}));

vi.mock("@/features/saved-tenders/services/savedTenders.service", () => ({
  fetchSavedTenders: vi.fn(),
  saveTenderApi: vi.fn(),
  unsaveTenderApi: vi.fn(),
}));

vi.mock("@/features/ranking-telemetry/services/rankingTelemetryService", () => ({
  reportTenderInteraction: vi.fn(),
}));

/** Abierta de verdad: la ficha esconde los botones de una licitación vencida. */
const EN_UN_MES = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString();

const tender: Tender = {
  id: "tender-50",
  code: "555-66-COT26",
  name: "Servicios de Seguridad y Redes",
  description: "Ciberseguridad integral",
  status_id: 2,
  status_code: "publicada",
  published_at: "2026-06-01T00:00:00Z",
  closing_at: EN_UN_MES,
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
};

const mockMatch: MatchingResult = {
  id: "match-50",
  supplier_id: "sup-1",
  tender_id: "tender-50",
  similarity_score: 0.95,
  reranker_score: 0.95,
  final_score: 0.95,
  model_version: "v1",
  calculated_at: "2026-06-01T00:00:00Z",
  tender,
};

function llamadasDe(kind: string) {
  return vi.mocked(reportTenderInteraction).mock.calls.filter((c) => c[1] === kind);
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(tenderService.getRecommendedTenders).mockResolvedValue([mockMatch]);
  vi.mocked(tenderService.getDeepAnalysisOnly).mockResolvedValue(null as never);
  vi.mocked(tenderService.calculateTenderScore).mockResolvedValue({ score_pct: 85 } as never);
  vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([]);
});

describe("TenderDetailView: telemetría del ranking", () => {
  it("pide las recomendadas con track: false para no crear un ranking fantasma", async () => {
    render(<TenderDetailView tenderId="tender-50" rankingContext={CTX} />);

    await screen.findByText("Servicios de Seguridad y Redes");

    expect(tenderService.getRecommendedTenders).toHaveBeenCalledWith("user-1", { track: false });
  });

  it("informa el detalle con el ranking de la URL", async () => {
    render(<TenderDetailView tenderId="tender-50" rankingContext={CTX} />);

    await screen.findByText("Servicios de Seguridad y Redes");

    await waitFor(() => {
      expect(reportTenderInteraction).toHaveBeenCalledWith(
        "tender-50",
        "detalle",
        "detalle",
        CTX,
      );
    });
    expect(llamadasDe("detalle")).toHaveLength(1);
  });

  it("sin ranking en la URL informa el detalle sin atribuir", async () => {
    render(<TenderDetailView tenderId="tender-50" />);

    await screen.findByText("Servicios de Seguridad y Redes");

    await waitFor(() => {
      expect(reportTenderInteraction).toHaveBeenCalledWith(
        "tender-50",
        "detalle",
        "detalle",
        null,
      );
    });
  });

  it("guardar informa 'guardar' cuando el guardado resultó", async () => {
    const user = userEvent.setup();
    vi.mocked(savedService.saveTenderApi).mockResolvedValue(undefined as never);
    render(<TenderDetailView tenderId="tender-50" rankingContext={CTX} />);

    await user.click(await screen.findByRole("button", { name: "Guardar licitación" }));

    await waitFor(() => {
      expect(reportTenderInteraction).toHaveBeenCalledWith(
        "tender-50",
        "guardar",
        "detalle",
        CTX,
      );
    });
  });

  it("un guardado que falla no informa 'guardar'", async () => {
    const user = userEvent.setup();
    vi.mocked(savedService.saveTenderApi).mockRejectedValue(new TypeError("Failed to fetch"));
    render(<TenderDetailView tenderId="tender-50" rankingContext={CTX} />);

    await user.click(await screen.findByRole("button", { name: "Guardar licitación" }));
    await screen.findByRole("alert");

    expect(llamadasDe("guardar")).toHaveLength(0);
  });

  it("quitar de guardadas no informa nada", async () => {
    const user = userEvent.setup();
    vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([mockMatch] as never);
    vi.mocked(savedService.unsaveTenderApi).mockResolvedValue(undefined as never);
    render(<TenderDetailView tenderId="tender-50" rankingContext={CTX} />);

    await user.click(
      await screen.findByRole("button", { name: "Quitar de licitaciones guardadas" }),
    );
    await waitFor(() => {
      expect(savedService.unsaveTenderApi).toHaveBeenCalled();
    });

    expect(llamadasDe("guardar")).toHaveLength(0);
  });

  it("un clic en la ficha oficial informa 'ficha_mp'", async () => {
    const user = userEvent.setup();
    render(<TenderDetailView tenderId="tender-50" rankingContext={CTX} />);

    const link = await screen.findByRole("link", { name: /Ficha oficial en Mercado Público/ });
    // jsdom no implementa la navegación.
    link.addEventListener("click", (e) => e.preventDefault());
    await user.click(link);

    expect(reportTenderInteraction).toHaveBeenCalledWith(
      "tender-50",
      "ficha_mp",
      "detalle",
      CTX,
    );
  });

  it("abrir el asistente dos veces informa una sola vez", async () => {
    const user = userEvent.setup();
    render(<TenderDetailView tenderId="tender-50" rankingContext={CTX} />);

    const boton = await screen.findByRole("button", { name: /Consultar asistente virtual/ });
    await user.click(boton);
    await user.click(boton);

    expect(llamadasDe("asistente")).toHaveLength(1);
    expect(llamadasDe("asistente")[0]).toEqual(["tender-50", "asistente", "detalle", CTX]);
  });

  it("el botón de análisis informa 'analisis' y navega", async () => {
    const user = userEvent.setup();
    render(<TenderDetailView tenderId="tender-50" rankingContext={CTX} />);

    await user.click(
      await screen.findByRole("button", { name: /Generar análisis de compatibilidad IA/ }),
    );

    expect(reportTenderInteraction).toHaveBeenCalledWith(
      "tender-50",
      "analisis",
      "detalle",
      CTX,
    );
    expect(mockRouter.push).toHaveBeenCalledWith("/matches/tender-50/analisis");
  });

  it("guardar la cotización informa 'cotizacion'", async () => {
    const user = userEvent.setup();
    render(<TenderDetailView tenderId="tender-50" rankingContext={CTX} />);

    await user.click(await screen.findByRole("button", { name: "Simular cotización guardada" }));

    expect(reportTenderInteraction).toHaveBeenCalledWith(
      "tender-50",
      "cotizacion",
      "detalle",
      CTX,
    );
  });

  it("subir un anexo informa 'anexo'", async () => {
    const user = userEvent.setup();
    render(<TenderDetailView tenderId="tender-50" rankingContext={CTX} />);

    await user.click(await screen.findByRole("button", { name: "Simular subida de anexo" }));

    expect(reportTenderInteraction).toHaveBeenCalledWith(
      "tender-50",
      "anexo",
      "detalle",
      CTX,
    );
  });
});
