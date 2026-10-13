import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TenderCard } from "../TenderCard";
import type { MatchingResult, Tender } from "../../tenderTypes";
import { formatClosingDate } from "../../utils/format";
import { reportTenderInteraction } from "@/features/ranking-telemetry/services/rankingTelemetryService";
import { resetReportedImpressions } from "@/features/ranking-telemetry/hooks/useImpressionTracker";

vi.mock("@/features/ranking-telemetry/services/rankingTelemetryService", () => ({
  reportTenderInteraction: vi.fn(),
}));

// Un <a> que no navega y llama al onClick original: en jsdom no hay router.
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: React.ComponentProps<"a"> & { href: string }) => (
    <a
      href={href}
      {...rest}
      onClick={(e) => {
        e.preventDefault();
        rest.onClick?.(e);
      }}
    >
      {children}
    </a>
  ),
}));

const RK = "0b6f3d2e-8f1a-4c53-9a6e-2d1c7b9e4a10";

beforeEach(() => {
  vi.clearAllMocks();
  resetReportedImpressions();
});

const mockTender: Tender = {
  id: "tender-123",
  code: "1234-56-COT26",
  name: "Adquisición de Insumos Médicos",
  description: "Descripción de prueba",
  status_id: 1,
  status_code: "publicada",
  published_at: "2026-06-01T10:00:00Z",
  closing_at: "2026-06-10T18:00:00Z",
  last_change_at: "2026-06-01T10:00:00Z",
  buyer_rut: "12345678-9",
  buyer_name: "Hospital Central",
  buyer_unit: "Abastecimiento",
  region: "Región Metropolitana de Santiago",
  province: "Santiago",
  commune: "Santiago",
  available_amount_clp: 5000000,
  created_at: "2026-06-01T10:00:00Z",
  updated_at: "2026-06-01T10:00:00Z",
  items: [],
};

const mockMatch: MatchingResult = {
  id: "match-123",
  supplier_id: "supplier-123",
  tender_id: "tender-123",
  similarity_score: 0.85,
  reranker_score: 0.85,
  final_score: 0.85,
  model_version: "v1",
  calculated_at: "2026-06-01T10:00:00Z",
  tender: mockTender,
};

describe("TenderCard", () => {
  it("renderiza el medidor de compatibilidad cuando se proporciona un match", () => {
    render(<TenderCard match={mockMatch} />);

    expect(screen.getByText("Alta compatibilidad")).toBeInTheDocument();
    expect(screen.getByText("85")).toBeInTheDocument();
    expect(screen.getByText("%")).toBeInTheDocument();
    expect(screen.getByText("Adquisición de Insumos Médicos")).toBeInTheDocument();
    expect(screen.getByText("Hospital Central")).toBeInTheDocument();
  });

  it("no renderiza el medidor de compatibilidad cuando solo se pasa tender", () => {
    render(<TenderCard tender={mockTender} />);

    expect(screen.queryByText("Alta compatibilidad")).not.toBeInTheDocument();
    expect(screen.queryByText("Baja compatibilidad")).not.toBeInTheDocument();
    expect(screen.queryByText("0%")).not.toBeInTheDocument();
    expect(screen.getByText("Adquisición de Insumos Médicos")).toBeInTheDocument();
    expect(screen.getByText("Hospital Central")).toBeInTheDocument();
  });

  it("muestra el estado real en la viñeta cuando la licitación no está activa", () => {
    // Con cierre futuro: la viñeta no puede decir "Cierra en N días" de una
    // licitación que ya se declaró desierta.
    render(
      <TenderCard
        tender={{ ...mockTender, status_code: "desierta", closing_at: "2099-01-01T12:00:00Z" }}
      />,
    );

    expect(screen.getByText("Desierta")).toBeInTheDocument();
    expect(screen.queryByText(/Cierra en/)).not.toBeInTheDocument();
  });
});

describe("TenderCard: segundo llamado", () => {
  it("etiqueta la licitación que está en su segundo llamado", () => {
    render(<TenderCard tender={{ ...mockTender, call_number: 2 }} />);

    expect(screen.getByText("Segundo llamado")).toBeInTheDocument();
  });

  it("no etiqueta el primer llamado aunque Mercado Público publique la fecha del segundo", () => {
    render(
      <TenderCard
        tender={{
          ...mockTender,
          call_number: 1,
          first_call_closing_at: "2026-06-10T18:00:00Z",
          second_call_closing_at: "2026-06-11T18:00:00Z",
        }}
      />,
    );

    expect(screen.queryByText("Segundo llamado")).not.toBeInTheDocument();
  });

  it("una licitación antigua, sin datos del llamado, se ve como antes", () => {
    render(
      <TenderCard
        tender={{
          ...mockTender,
          call_number: null,
          first_call_closing_at: null,
          second_call_closing_at: null,
        }}
      />,
    );

    expect(screen.queryByText("Segundo llamado")).not.toBeInTheDocument();
    expect(
      screen.getByText(`Cierra ${formatClosingDate(mockTender.closing_at)}`),
    ).toBeInTheDocument();
  });
});

describe("TenderCard: telemetría del ranking", () => {
  it("el enlace lleva el ranking y la posición mostrada", () => {
    render(
      <TenderCard
        match={mockMatch}
        ranking={{ rankingId: RK, position: 4, source: "matches" }}
      />,
    );

    expect(screen.getByRole("link")).toHaveAttribute(
      "href",
      `/matches/tender-123?r=${RK}&p=4`,
    );
  });

  it("sin ranking el enlace es el de siempre y un clic no reporta nada", async () => {
    const user = userEvent.setup();
    render(<TenderCard match={mockMatch} />);

    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "/matches/tender-123");
    await user.click(link);

    expect(reportTenderInteraction).not.toHaveBeenCalled();
  });

  it("con ranking, un clic marca la impresión (probó que la vio) pero no el detalle", async () => {
    const user = userEvent.setup();
    render(
      <TenderCard
        match={mockMatch}
        ranking={{ rankingId: RK, position: 4, source: "matches" }}
      />,
    );

    await user.click(screen.getByRole("link"));

    expect(reportTenderInteraction).toHaveBeenCalledTimes(1);
    expect(reportTenderInteraction).toHaveBeenCalledWith("tender-123", "impresion", "matches", {
      rankingId: RK,
      position: 4,
    });
  });

  it("guardar con ranking reporta 'guardar' y llama a onToggleSave", async () => {
    const user = userEvent.setup();
    const onToggleSave = vi.fn();
    render(
      <TenderCard
        match={mockMatch}
        isSaved={false}
        onToggleSave={onToggleSave}
        ranking={{ rankingId: RK, position: 2, source: "inicio" }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Guardar licitación" }));

    expect(onToggleSave).toHaveBeenCalledWith("tender-123");
    expect(reportTenderInteraction).toHaveBeenCalledTimes(1);
    expect(reportTenderInteraction).toHaveBeenCalledWith("tender-123", "guardar", "inicio", {
      rankingId: RK,
      position: 2,
    });
  });

  it("quitar de guardadas no reporta nada", async () => {
    const user = userEvent.setup();
    const onToggleSave = vi.fn();
    render(
      <TenderCard
        match={mockMatch}
        isSaved
        onToggleSave={onToggleSave}
        ranking={{ rankingId: RK, position: 2, source: "inicio" }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Quitar de licitaciones guardadas" }));

    expect(onToggleSave).toHaveBeenCalledWith("tender-123");
    expect(reportTenderInteraction).not.toHaveBeenCalled();
  });
});
