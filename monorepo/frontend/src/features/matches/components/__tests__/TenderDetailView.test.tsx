import React from "react";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TenderDetailView } from "../TenderDetailView";
import * as tenderService from "../../services/tenderService";
import * as savedService from "@/features/saved-tenders/services/savedTenders.service";
import { SAVED_TENDERS_ERRORS } from "@/features/saved-tenders/constants";
import type { DeepAnalysis, MatchingResult, Tender } from "../../tenderTypes";
import { formatDateTime, normalizeScore } from "../../utils/format";
import type { TenderDetail } from "@/features/notifications/notificationTypes";

const mockRouter = {
  push: vi.fn(),
  replace: vi.fn(),
  back: vi.fn(),
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
  TenderAssistantDrawer: ({ onDocumentsChanged }: { onDocumentsChanged?: () => void }) => (
    <button type="button" onClick={onDocumentsChanged}>
      simular subida de bases
    </button>
  ),
}));

vi.mock("@/features/proposals/components/ProposalEntryCard", () => ({
  ProposalEntryCard: ({ isClosed }: { isClosed: boolean }) => (
    <div data-testid="proposal-entry-card">{String(isClosed)}</div>
  ),
}));

vi.mock("@/features/tender-milestones/components/MilestonesSection", () => ({
  MilestonesSection: ({ tenderId, refreshKey }: { tenderId: string; refreshKey?: number }) => (
    <div data-testid="milestones-section" data-refresh-key={refreshKey}>
      {tenderId}
    </div>
  ),
}));

// Sin este mock, el panel real llamaría a `apiFetch` en jsdom.
vi.mock("@/features/tender-attachments/components/TenderAttachmentsPanel", () => ({
  TenderAttachmentsPanel: ({
    tenderId,
    tenderCode,
    onReadyKeyChange,
    onUploadSuccess,
    onAnalysisFinished,
  }: {
    tenderId: string;
    tenderCode: string;
    onReadyKeyChange?: (k: string) => void;
    onUploadSuccess?: () => void;
    onAnalysisFinished?: () => void;
  }) => (
    <div data-testid="tender-attachments-panel">
      <span>{`${tenderId}|${tenderCode}`}</span>
      <button
        type="button"
        data-testid="mock-simulate-attachment-upload"
        onClick={() => {
          onReadyKeyChange?.("anexo-1-ready");
          onUploadSuccess?.();
        }}
      >
        Simular subida
      </button>
      <button type="button" onClick={() => onAnalysisFinished?.()}>
        Simular análisis terminado
      </button>
    </div>
  ),
}));

vi.mock("@/features/tender-attachments/components/DigestCard", () => ({
  DigestCard: ({ tenderId, refreshKey }: { tenderId: string; refreshKey?: string }) => (
    <div data-testid="digest-card" data-refresh-key={refreshKey}>
      {tenderId}
    </div>
  ),
}));

vi.mock("@/features/saved-tenders/services/savedTenders.service", () => ({
  fetchSavedTenders: vi.fn(),
  saveTenderApi: vi.fn(),
  unsaveTenderApi: vi.fn(),
}));

// La telemetría del ranking tiene sus propias pruebas (TenderDetailView.telemetry);
// acá se aísla para que ninguna prueba salga a la red.
vi.mock("@/features/ranking-telemetry/services/rankingTelemetryService", () => ({
  reportTenderInteraction: vi.fn(),
}));

vi.mock("@/features/tender-export/components/ExportActions", () => ({
  ExportActions: ({ tenderId }: { tenderId: string }) => (
    <div data-testid="exportar">Exportar {tenderId}</div>
  ),
}));

// El diálogo tiene sus propios tests; acá solo importa que la ficha lo abra.
vi.mock("@/features/tender-sharing/components/ShareDialog", () => ({
  ShareDialog: ({ open, tenderId }: { open: boolean; tenderId: string }) =>
    open ? <div role="dialog" aria-label={`Compartir ${tenderId}`} /> : null,
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

/**
 * Respuesta de `GET /tenders/{id}` para una licitación del ranking. La ficha ya
 * no pide la lista de recomendadas: el detalle le dice si está en ella.
 */
function detalleDe(match: MatchingResult, isRecommended = true): TenderDetail {
  return {
    tender: match.tender as Tender,
    score_pct:
      match.final_score !== null ? Math.round(normalizeScore(match.final_score)) : null,
    is_closed: false,
    is_recommended: isRecommended,
  };
}

describe("TenderDetailView (CA-5: Rollback y notificación en error de red)", () => {
  const user = userEvent.setup();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(tenderService.getTenderDetail).mockResolvedValue(detalleDe(mockMatch));
    vi.mocked(tenderService.getDeepAnalysisOnly).mockResolvedValue(null as never);
  });

  it("muestra los hitos de la licitación en la sección de fechas importantes", async () => {
    vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([]);

    render(<TenderDetailView tenderId="tender-50" />);

    expect(await screen.findByText("Hitos y fechas importantes")).toBeInTheDocument();
    expect(screen.getByTestId("milestones-section")).toHaveTextContent("tender-50");
  });

  it("muestra el resumen de anexos en la sección de entrega y requisitos", async () => {
    vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([]);

    render(<TenderDetailView tenderId="tender-50" />);

    expect(await screen.findByText("Entrega y requisitos")).toBeInTheDocument();
    expect(screen.getByTestId("digest-card")).toHaveTextContent("tender-50");
  });

  it("al subir bases en el asistente recarga la tabla de hitos (HU-16)", async () => {
    vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([]);
    render(<TenderDetailView tenderId="tender-50" />);
    const seccion = await screen.findByTestId("milestones-section");
    const antes = seccion.getAttribute("data-refresh-key");

    await user.click(screen.getByRole("button", { name: "simular subida de bases" }));

    expect(screen.getByTestId("milestones-section").getAttribute("data-refresh-key")).not.toBe(antes);
  });

  it("al subir un anexo recarga la tabla de hitos (plan 233)", async () => {
    vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([]);
    render(<TenderDetailView tenderId="tender-50" />);
    const seccion = await screen.findByTestId("milestones-section");
    const antes = seccion.getAttribute("data-refresh-key");

    await user.click(screen.getByTestId("mock-simulate-attachment-upload"));

    expect(screen.getByTestId("milestones-section").getAttribute("data-refresh-key")).not.toBe(antes);
  });

  it("cuando termina el análisis de los anexos vuelve a leer el análisis (plan 233)", async () => {
    vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([]);
    vi.mocked(tenderService.getDeepAnalysisOnly).mockResolvedValue(null as never);
    render(<TenderDetailView tenderId="tender-50" />);
    await screen.findByTestId("milestones-section");
    await waitFor(() => expect(tenderService.getDeepAnalysisOnly).toHaveBeenCalledTimes(1));

    await user.click(screen.getByRole("button", { name: "Simular análisis terminado" }));

    await waitFor(() => expect(tenderService.getDeepAnalysisOnly).toHaveBeenCalledTimes(2));
  });

  it("monta la entrada a la postulación (HU-20)", async () => {
    vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([]);

    render(<TenderDetailView tenderId="tender-50" />);

    expect(await screen.findByTestId("proposal-entry-card")).toBeInTheDocument();
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
    // El cotizador vive en la postulación (HU-20), no en la ficha.
    expect(screen.queryByRole("button", { name: "Generar cotización" })).not.toBeInTheDocument();
    await user.click(saveButton);

    const alert = await screen.findByText(SAVED_TENDERS_ERRORS.SAVE_FAILED);
    expect(alert).toBeInTheDocument();
    expect(alert).toHaveTextContent(
      /la operación no pudo realizarse y se mantuvo el estado anterior/i,
    );

    // Rollback: el botón vuelve a estar desmarcado
    expect(screen.getByRole("button", { name: "Guardar licitación" })).toBeInTheDocument();
  });

  it("el botón Compartir abre el diálogo de la licitación (HdU 19)", async () => {
    vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([]);
    render(<TenderDetailView tenderId="tender-50" />);
    await screen.findByText("Servicios de Seguridad y Redes");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Compartir licitación" }));

    expect(screen.getByRole("dialog", { name: "Compartir tender-50" })).toBeInTheDocument();
  });

  it("ofrece exportar la licitación a PDF y Excel (HdU 19)", async () => {
    vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([]);
    render(<TenderDetailView tenderId="tender-50" />);

    expect(await screen.findByTestId("exportar")).toHaveTextContent("Exportar tender-50");
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
    vi.mocked(tenderService.getDeepAnalysisOnly).mockResolvedValue(null as never);
    vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([]);
    vi.mocked(tenderService.getTenderDetail).mockResolvedValue({
      tender: tenderFueraDelTop,
      score_pct: null,
      is_closed: false,
      is_recommended: false,
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
      is_recommended: false,
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

  it("marca el análisis como desactualizado si el puntaje recalculado cambió", async () => {
    vi.mocked(tenderService.getDeepAnalysisOnly).mockResolvedValue(analisisGuardado);
    // Ya tenía 64% calculado, que es el puntaje que justifica el análisis.
    vi.mocked(tenderService.getTenderDetail).mockResolvedValue({
      tender: tenderFueraDelTop,
      score_pct: 64,
      is_closed: false,
      is_recommended: false,
    });
    vi.mocked(tenderService.calculateTenderScore).mockResolvedValue({
      score_pct: 73,
      calculated_at: "2026-09-16T10:00:00Z",
    });

    render(<TenderDetailView tenderId="tender-77" />);

    await user.click(await screen.findByRole("button", { name: /recalcular/i }));

    // 64% en la justificación y 73% en el medidor no pueden convivir como si
    // ambos estuvieran vigentes.
    expect(
      await screen.findByText("Este análisis está desactualizado")
    ).toBeInTheDocument();
  });

  it("no ofrece calcular ni generar en una licitación cerrada", async () => {
    vi.mocked(tenderService.getTenderDetail).mockResolvedValue({
      tender: tenderFueraDelTop,
      score_pct: null,
      is_closed: true,
      is_recommended: false,
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
    vi.mocked(tenderService.getTenderDetail).mockResolvedValue(
      detalleDe({
        ...mockMatch,
        tender: { ...(mockMatch.tender as Tender), closing_at: EN_UN_MES },
        final_score: 0.91,
      }),
    );
  });

  it("no ofrece recalcular: ese puntaje lo mantiene el ranking", async () => {
    render(<TenderDetailView tenderId="tender-50" />);

    expect(
      await screen.findByRole("img", { name: "Compatibilidad 91%" })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /recalcular/i })
    ).not.toBeInTheDocument();
    // El detalle ya dice si es recomendada: pedir el ranking completo para
    // buscarla en él podía disparar un re-ranking entero por abrir una ficha.
    expect(tenderService.getRecommendedTenders).not.toHaveBeenCalled();
  });
});

describe("TenderDetailView: volver", () => {
  const user = userEvent.setup();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([]);
    vi.mocked(tenderService.getDeepAnalysisOnly).mockResolvedValue(null as never);
    vi.mocked(tenderService.getTenderDetail).mockResolvedValue(detalleDe(mockMatch));
  });

  it("vuelve a la pantalla anterior, no siempre a los matches", async () => {
    // A la misma ficha se llega desde el buscador, las guardadas o una alerta:
    // mandar a todos a /matches descarta la búsqueda recién hecha.
    // jsdom abre cada prueba con una sola entrada; acá interesa el caso
    // normal, el de alguien que ya venía navegando.
    vi.spyOn(window.history, "length", "get").mockReturnValue(3);

    render(<TenderDetailView tenderId="tender-50" />);

    await user.click(await screen.findByRole("button", { name: /volver/i }));

    expect(mockRouter.back).toHaveBeenCalledTimes(1);
    expect(mockRouter.push).not.toHaveBeenCalled();
  });
});

describe("TenderDetailView: anexos oficiales", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([]);
    vi.mocked(tenderService.getDeepAnalysisOnly).mockResolvedValue(null as never);
    vi.mocked(tenderService.getTenderDetail).mockResolvedValue(detalleDe(mockMatch));
  });

  it("muestra el panel de anexos en la sección Documentos, antes de la tarjeta de análisis IA", async () => {
    render(<TenderDetailView tenderId="tender-50" />);

    const panel = await screen.findByTestId("tender-attachments-panel");
    expect(panel).toHaveTextContent("tender-50|555-66-COT26");
    // Desde la HU-30 los anexos viven en su propia sección, bajo la grilla de métricas.
    const documentos = screen.getByText("Documentos").parentElement as HTMLElement;
    expect(documentos).toContainElement(panel);
    expect(
      panel.compareDocumentPosition(
        screen.getByRole("heading", { name: "Análisis de compatibilidad IA" }),
      ) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("ya no tiene la sección 'Documentos asociados'", async () => {
    render(<TenderDetailView tenderId="tender-50" />);

    await screen.findByTestId("tender-attachments-panel");
    expect(screen.queryByText("Documentos asociados")).not.toBeInTheDocument();
    // El enlace vive ahora en el panel, que acá está mockeado.
    expect(
      screen.queryByRole("link", { name: /ver documentos en mercado público/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /ficha oficial en mercado público/i }),
    ).toBeInTheDocument();
  });
});

/**
 * `Intl` separa la hora del "p. m." con un espacio duro o uno fino según la
 * versión de Node, y el matcher de Testing Library no normaliza el string
 * esperado. Escritos como escapes: en el código fuente son indistinguibles.
 */
function conEspaciosNormales(valor: string): string {
  return valor.replace(/[\u00a0\u202f]/g, " ");
}

describe("TenderDetailView: segundo llamado", () => {
  // Octubre es UTC-3 en Chile: 13:30 y 13:40.
  const PRIMER = "2026-10-06T16:30:00Z";
  const SEGUNDO = "2026-10-07T16:40:00Z";

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([]);
    vi.mocked(tenderService.getDeepAnalysisOnly).mockResolvedValue(null as never);
  });

  function conTender(cambios: Partial<Tender>) {
    vi.mocked(tenderService.getTenderDetail).mockResolvedValue(
      detalleDe({ ...mockMatch, tender: { ...(mockMatch.tender as Tender), ...cambios } }),
    );
  }

  it("en segundo llamado el encabezado no repite la etiqueta", async () => {
    conTender({ call_number: 2 });

    render(<TenderDetailView tenderId="tender-50" />);

    const encabezado = (await screen.findByRole("heading", { level: 1 })).closest("header");
    expect(encabezado).not.toBeNull();
    expect(within(encabezado as HTMLElement).queryByText("Segundo llamado")).not.toBeInTheDocument();
  });

  it("en segundo llamado etiqueta la ficha y muestra el cierre de cada llamado", async () => {
    conTender({
      call_number: 2,
      first_call_closing_at: PRIMER,
      second_call_closing_at: SEGUNDO,
      closing_at: SEGUNDO,
    });

    render(<TenderDetailView tenderId="tender-50" />);

    const llamado = await screen.findByText("Llamado");
    expect(within(llamado.parentElement as HTMLElement).getByText("Segundo llamado")).toBeInTheDocument();
    const region = screen.getByRole("region", { name: "Cierre por llamado" });
    expect(within(region).getByText("Cierre 1.er llamado")).toBeInTheDocument();
    expect(within(region).getByText(conEspaciosNormales(formatDateTime(PRIMER)))).toBeInTheDocument();
    expect(within(region).getByText("Cierre 2.º llamado")).toBeInTheDocument();
    expect(within(region).getByText(conEspaciosNormales(formatDateTime(SEGUNDO)))).toBeInTheDocument();
    expect(screen.queryByText("Segundo llamado posible")).not.toBeInTheDocument();
  });

  it("en primer llamado la fecha del segundo se presenta como posible, sin etiqueta de segundo llamado", async () => {
    conTender({
      call_number: 1,
      first_call_closing_at: PRIMER,
      second_call_closing_at: SEGUNDO,
    });

    render(<TenderDetailView tenderId="tender-50" />);

    expect(await screen.findByText("Servicios de Seguridad y Redes")).toBeInTheDocument();
    // Coincidencia exacta: "Segundo llamado posible" no cuenta como la etiqueta.
    expect(screen.getByText("Primer llamado")).toBeInTheDocument();
    expect(screen.queryByText("Segundo llamado")).not.toBeInTheDocument();
    const region = screen.getByRole("region", { name: "Cierre por llamado" });
    expect(within(region).getByText("Segundo llamado posible")).toBeInTheDocument();
    expect(within(region).getByText(conEspaciosNormales(formatDateTime(SEGUNDO)))).toBeInTheDocument();
  });

  it("una licitación antigua, sin los campos, se ve como antes", async () => {
    conTender({});

    render(<TenderDetailView tenderId="tender-50" />);

    expect(await screen.findByText("Servicios de Seguridad y Redes")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Cierre por llamado" })).not.toBeInTheDocument();
    // La tarjeta no afirma ningún llamado: dice que no hay dato.
    const llamado = screen.getByText("Llamado").parentElement as HTMLElement;
    expect(within(llamado).getByText("No disponible")).toBeInTheDocument();
    expect(screen.queryByText("Segundo llamado")).not.toBeInTheDocument();
    expect(screen.queryByText("Segundo llamado posible")).not.toBeInTheDocument();
  });

  it("con los tres campos en null tampoco dibuja nada", async () => {
    conTender({ call_number: null, first_call_closing_at: null, second_call_closing_at: null });

    render(<TenderDetailView tenderId="tender-50" />);

    expect(await screen.findByText("Servicios de Seguridad y Redes")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Cierre por llamado" })).not.toBeInTheDocument();
    // La tarjeta no afirma ningún llamado: dice que no hay dato.
    const llamado = screen.getByText("Llamado").parentElement as HTMLElement;
    expect(within(llamado).getByText("No disponible")).toBeInTheDocument();
    expect(screen.queryByText("Segundo llamado")).not.toBeInTheDocument();
    expect(screen.queryByText("Segundo llamado posible")).not.toBeInTheDocument();
  });

  it("recalcula automáticamente el puntaje de compatibilidad cuando se suben anexos", async () => {
    conTender({});
    vi.mocked(tenderService.calculateTenderScore).mockResolvedValueOnce({
      score_pct: 88,
      calculated_at: new Date().toISOString(),
    });

    render(<TenderDetailView tenderId="tender-50" />);
    await screen.findByTestId("tender-attachments-panel");

    const btnSimular = screen.getByTestId("mock-simulate-attachment-upload");
    await userEvent.setup().click(btnSimular);

    await waitFor(() => {
      expect(tenderService.calculateTenderScore).toHaveBeenCalledWith("tender-50");
    });
    expect(
      await screen.findByRole("img", { name: "Compatibilidad 88%" }),
    ).toBeInTheDocument();
  });
});

describe("TenderDetailView: grilla de métricas", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([]);
    vi.mocked(tenderService.getDeepAnalysisOnly).mockResolvedValue(null as never);
  });

  function conTender(cambios: Partial<Tender>) {
    vi.mocked(tenderService.getTenderDetail).mockResolvedValue(
      detalleDe({ ...mockMatch, tender: { ...(mockMatch.tender as Tender), ...cambios } }),
    );
  }

  /** La tarjeta que lleva ese título (el título está en el primer hijo), para no confundirla con otro texto de la ficha. */
  async function tarjeta(titulo: string): Promise<HTMLElement> {
    const eyebrow = await screen.findByText(titulo);
    return eyebrow.parentElement as HTMLElement;
  }

  describe("cotizaciones recibidas", () => {
    it("una cifra de 0 se muestra como 0", async () => {
      conTender({ received_offers_count: 0 });

      render(<TenderDetailView tenderId="tender-50" />);

      const card = await tarjeta("Cotizaciones recibidas");
      expect(within(card).getByText("0 cotizaciones")).toBeInTheDocument();
    });

    it("una cifra mayor a 0 se muestra tal cual", async () => {
      conTender({ received_offers_count: 17 });

      render(<TenderDetailView tenderId="tender-50" />);

      const card = await tarjeta("Cotizaciones recibidas");
      expect(within(card).getByText("17 cotizaciones")).toBeInTheDocument();
    });

    it.each([
      ["null", { received_offers_count: null }],
      ["ausente", {}],
    ])("con la cifra %s dice que no está disponible y no muestra un 0", async (_caso, cambios) => {
      conTender(cambios);

      render(<TenderDetailView tenderId="tender-50" />);

      const card = await tarjeta("Cotizaciones recibidas");
      expect(within(card).getByText("No disponible")).toBeInTheDocument();
      expect(screen.queryByText("0 cotizaciones")).not.toBeInTheDocument();
    });
  });

  describe("secciones de entrega y de descripción", () => {
    const ITEM = {
      id: "item-1",
      name: "Firewall perimetral",
      description: null,
      quantity: 2,
      unit_of_measure: "unidad",
    } as unknown as Tender["items"][number];

    it("entrega y requisitos agrupa los cierres por llamado, los ítems y el resumen de anexos", async () => {
      conTender({
        call_number: 1,
        first_call_closing_at: "2026-10-06T16:30:00Z",
        second_call_closing_at: "2026-10-07T16:40:00Z",
        items: [ITEM],
      });

      render(<TenderDetailView tenderId="tender-50" />);

      const entrega = (await screen.findByText("Entrega y requisitos")).parentElement as HTMLElement;
      expect(within(entrega).getByRole("region", { name: "Cierre por llamado" })).toBeInTheDocument();
      expect(within(entrega).getByText("Firewall perimetral")).toBeInTheDocument();
      expect(within(entrega).getByTestId("digest-card")).toBeInTheDocument();
      expect(within(entrega).queryByText("Ciberseguridad integral")).not.toBeInTheDocument();
    });

    it("descripción lleva solo el texto de la licitación", async () => {
      conTender({ items: [ITEM] });

      render(<TenderDetailView tenderId="tender-50" />);

      const descripcion = (await screen.findByText("Descripción")).parentElement as HTMLElement;
      expect(within(descripcion).getByText("Ciberseguridad integral")).toBeInTheDocument();
      expect(within(descripcion).queryByText("Firewall perimetral")).not.toBeInTheDocument();
      expect(within(descripcion).queryByTestId("digest-card")).not.toBeInTheDocument();
    });
  });

  describe("orden de la ficha", () => {
    /** `a` aparece antes que `b` en el documento. */
    function antes(a: Node, b: Node): boolean {
      return Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
    }

    it("las secciones van como entrega y requisitos, documentos y descripción", async () => {
      conTender({});

      render(<TenderDetailView tenderId="tender-50" />);

      const entrega = await screen.findByText("Entrega y requisitos");
      const documentos = screen.getByText("Documentos");
      const descripcion = screen.getByText("Descripción");
      expect(antes(entrega, documentos)).toBe(true);
      expect(antes(documentos, descripcion)).toBe(true);
    });

    it("los anexos están dentro de la sección de documentos", async () => {
      conTender({});

      render(<TenderDetailView tenderId="tender-50" />);

      const documentos = (await screen.findByText("Documentos")).parentElement as HTMLElement;
      expect(within(documentos).getByTestId("tender-attachments-panel")).toBeInTheDocument();
    });

    it("la grilla de métricas queda justo debajo del encabezado", async () => {
      conTender({});

      render(<TenderDetailView tenderId="tender-50" />);

      const encabezado = (await screen.findByRole("heading", { level: 1 })).closest("header") as HTMLElement;
      const grilla = (await tarjeta("Monto estimado")).parentElement as HTMLElement;
      expect(encabezado.nextElementSibling).toBe(grilla);
    });
  });

  describe("composición de la grilla", () => {
    it("tiene exactamente cuatro tarjetas y ninguna es la publicación", async () => {
      conTender({});

      render(<TenderDetailView tenderId="tender-50" />);

      const grilla = (await tarjeta("Monto estimado")).parentElement as HTMLElement;
      const titulos = Array.from(grilla.children).map((c) => c.firstElementChild?.textContent);
      expect(titulos).toEqual(["Monto estimado", "Cierre", "Llamado", "Cotizaciones recibidas"]);
      expect(grilla).toHaveClass("lg:grid-cols-4");
      expect(screen.queryByText("Publicación")).not.toBeInTheDocument();
    });

    it("la fecha de publicación aparece en hitos y fechas importantes", async () => {
      const PUBLICADA = "2026-06-02T15:00:00Z";
      conTender({ published_at: PUBLICADA, last_change_at: "2026-06-05T15:00:00Z" });

      render(<TenderDetailView tenderId="tender-50" />);

      const seccion = (await screen.findByText("Hitos y fechas importantes")).parentElement as HTMLElement;
      expect(conEspaciosNormales(seccion.textContent ?? "")).toContain(
        `Publicada en Mercado Público: ${conEspaciosNormales(formatDateTime(PUBLICADA))}`,
      );
    });
  });

  describe("tarjeta del llamado", () => {
    it("el primer llamado se muestra en tono informativo", async () => {
      conTender({ call_number: 1 });

      render(<TenderDetailView tenderId="tender-50" />);

      const card = await tarjeta("Llamado");
      expect(within(card).getByText("Primer llamado")).toHaveAttribute("data-tone", "info");
    });

    it("el segundo llamado se muestra como advertencia", async () => {
      conTender({ call_number: 2 });

      render(<TenderDetailView tenderId="tender-50" />);

      const card = await tarjeta("Llamado");
      expect(within(card).getByText("Segundo llamado")).toHaveAttribute("data-tone", "warning");
    });

    it.each([
      ["null", { call_number: null }],
      ["ausente", {}],
    ])("con el llamado %s dice que no está disponible", async (_caso, cambios) => {
      conTender(cambios);

      render(<TenderDetailView tenderId="tender-50" />);

      const card = await tarjeta("Llamado");
      expect(within(card).getByText("No disponible")).toHaveAttribute("data-tone", "neutral");
    });
  });

  describe("fecha de revisión de las cotizaciones", () => {
    const REVISADO = "2026-10-25T17:05:00Z";

    it("con cifra y fecha dice cuándo se revisó", async () => {
      conTender({ received_offers_count: 17, offers_checked_at: REVISADO });

      render(<TenderDetailView tenderId="tender-50" />);

      const card = await tarjeta("Cotizaciones recibidas");
      expect(conEspaciosNormales(card.textContent ?? "")).toContain(
        `Revisado el ${conEspaciosNormales(formatDateTime(REVISADO))}`,
      );
    });

    it("con un 0 y fecha también lo dice: el 0 es una cifra real", async () => {
      conTender({ received_offers_count: 0, offers_checked_at: REVISADO });

      render(<TenderDetailView tenderId="tender-50" />);

      const card = await tarjeta("Cotizaciones recibidas");
      expect(card.textContent).toContain("Revisado el");
    });

    it.each([
      ["sin cifra", { received_offers_count: null, offers_checked_at: REVISADO }],
      ["sin fecha", { received_offers_count: 17, offers_checked_at: null }],
      ["sin ninguna de las dos", {}],
    ])("%s no muestra la pista", async (_caso, cambios) => {
      conTender(cambios);

      render(<TenderDetailView tenderId="tender-50" />);

      await tarjeta("Cotizaciones recibidas");
      expect(screen.queryByText(/Revisado el/)).not.toBeInTheDocument();
    });
  });

  describe("cotizaciones de los dos llamados", () => {
    const REVISADO = "2026-10-25T17:05:00Z";

    it("en segundo llamado suma los dos y desglosa junto a la revisión", async () => {
      conTender({
        call_number: 2,
        received_offers_count: 2,
        first_call_offers_count: 5,
        offers_checked_at: REVISADO,
      });

      render(<TenderDetailView tenderId="tender-50" />);

      const card = await tarjeta("Cotizaciones recibidas");
      const texto = conEspaciosNormales(card.textContent ?? "");
      expect(within(card).getByText("7 cotizaciones")).toBeInTheDocument();
      expect(texto).toContain("5 en el 1.er llamado y 2 en el 2.º");
      expect(texto).toContain(`Revisado el ${conEspaciosNormales(formatDateTime(REVISADO))}`);
    });

    it("sin la cifra del primer llamado muestra solo la del segundo", async () => {
      conTender({ call_number: 2, received_offers_count: 2, first_call_offers_count: null });

      render(<TenderDetailView tenderId="tender-50" />);

      const card = await tarjeta("Cotizaciones recibidas");
      expect(within(card).getByText("2 en el 2.º llamado")).toBeInTheDocument();
      expect(card.textContent).toContain("1.er llamado: No disponible");
    });
  });
});
