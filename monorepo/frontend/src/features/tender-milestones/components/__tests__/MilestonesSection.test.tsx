import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/features/shared/api/client";
import * as service from "../../services/milestonesService";
import { buildMilestone, buildMilestoneList } from "../../test-utils";
import { MilestonesSection } from "../MilestonesSection";

vi.mock("../../services/milestonesService", () => ({
  getTenderMilestones: vi.fn(),
  extractTenderMilestones: vi.fn(),
}));

const AHORA = new Date("2026-10-01T15:00:00Z");

function filas() {
  return screen.getAllByRole("row").slice(1); // sin la cabecera
}

describe("MilestonesSection", () => {
  beforeEach(() => {
    vi.mocked(service.getTenderMilestones).mockReset();
    vi.mocked(service.extractTenderMilestones).mockReset();
  });

  it("muestra los hitos en una tabla con fecha, origen y plazo destacado", async () => {
    vi.mocked(service.getTenderMilestones).mockResolvedValue(
      buildMilestoneList({
        milestones: [
          buildMilestone({
            id: "m-1",
            kind: "visita_tecnica",
            title: "Visita técnica obligatoria",
            source: "ia_documento",
            due_at: "2026-10-03T18:00:00Z",
            urgency: "critico",
            source_excerpt: "a las 15:00 del día 3",
          }),
          buildMilestone({ id: "m-2", due_at: "2026-10-20T18:00:00Z", urgency: "normal" }),
        ],
      }),
    );

    render(<MilestonesSection tenderId="t-1" now={AHORA} />);

    await waitFor(() => expect(filas()).toHaveLength(2));
    const visita = within(filas()[0]);
    expect(visita.getByText("Visita técnica obligatoria")).toBeInTheDocument();
    expect(visita.getByText("Visita técnica")).toBeInTheDocument();
    expect(visita.getByText("Extraído por IA")).toBeInTheDocument();
    expect(visita.getByText("03 oct 2026, 15:00")).toBeInTheDocument();
    expect(visita.getByText("En 2 días")).toBeInTheDocument();
    expect(visita.getByText("a las 15:00 del día 3")).toBeInTheDocument();
    expect(within(filas()[1]).getByText("Mercado Público")).toBeInTheDocument();
  });

  it("indica cuando un hito no tiene hora exacta", async () => {
    vi.mocked(service.getTenderMilestones).mockResolvedValue(
      buildMilestoneList({
        milestones: [buildMilestone({ due_at: "2026-10-20T03:00:00Z", has_time: false })],
      }),
    );

    render(<MilestonesSection tenderId="t-1" now={AHORA} />);

    expect(await screen.findByText("20 oct 2026")).toBeInTheDocument();
    expect(screen.getByText("Sin hora exacta")).toBeInTheDocument();
  });

  it("marca los hitos ya sincronizados con Google Calendar", async () => {
    vi.mocked(service.getTenderMilestones).mockResolvedValue(
      buildMilestoneList({ milestones: [buildMilestone({ synced_providers: ["google"] })] }),
    );

    render(<MilestonesSection tenderId="t-1" now={AHORA} />);

    expect(await screen.findByText("En Google Calendar")).toBeInTheDocument();
  });

  it("sin documentos subidos explica cómo extraer más hitos y no permite extraer", async () => {
    vi.mocked(service.getTenderMilestones).mockResolvedValue(buildMilestoneList({ documents_count: 0 }));

    render(<MilestonesSection tenderId="t-1" now={AHORA} />);

    const boton = await screen.findByRole("button", { name: /extraer hitos de las bases/i });
    expect(boton).toBeDisabled();
    expect(screen.getByText(/adjunta las bases en el asistente/i)).toBeInTheDocument();
  });

  it("extrae los hitos de las bases y muestra el resultado", async () => {
    const user = userEvent.setup();
    vi.mocked(service.getTenderMilestones).mockResolvedValue(buildMilestoneList({ documents_count: 1 }));
    vi.mocked(service.extractTenderMilestones).mockResolvedValue(
      buildMilestoneList({
        documents_count: 1,
        discarded_count: 1,
        milestones: [
          buildMilestone(),
          buildMilestone({ id: "m-2", kind: "entrega", title: "Entrega de muestras", source: "ia_documento" }),
        ],
      }),
    );
    render(<MilestonesSection tenderId="t-1" now={AHORA} />);

    await user.click(await screen.findByRole("button", { name: /extraer hitos de las bases/i }));

    expect(await screen.findByText("Entrega de muestras")).toBeInTheDocument();
    expect(screen.getByText("1 fecha no se pudo interpretar y se omitió.")).toBeInTheDocument();
    expect(service.extractTenderMilestones).toHaveBeenCalledWith("t-1");
  });

  it("si la extracción falla muestra el error y permite reintentar", async () => {
    const user = userEvent.setup();
    vi.mocked(service.getTenderMilestones).mockResolvedValue(buildMilestoneList({ documents_count: 1 }));
    vi.mocked(service.extractTenderMilestones)
      .mockRejectedValueOnce(new ApiError(503, "No se pudieron extraer los hitos de las bases en este momento."))
      .mockResolvedValueOnce(buildMilestoneList({ documents_count: 1 }));
    render(<MilestonesSection tenderId="t-1" now={AHORA} />);

    await user.click(await screen.findByRole("button", { name: /extraer hitos de las bases/i }));

    const alerta = await screen.findByRole("alert");
    expect(alerta).toHaveTextContent("No se pudieron extraer los hitos de las bases en este momento.");
    await user.click(within(alerta).getByRole("button", { name: "Reintentar" }));
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
    expect(service.extractTenderMilestones).toHaveBeenCalledTimes(2);
  });

  it("si no se pueden cargar los hitos muestra el error con reintento", async () => {
    const user = userEvent.setup();
    vi.mocked(service.getTenderMilestones)
      .mockRejectedValueOnce(new ApiError(500, "Error del servidor"))
      .mockResolvedValueOnce(buildMilestoneList());
    render(<MilestonesSection tenderId="t-1" now={AHORA} />);

    const alerta = await screen.findByRole("alert");
    expect(alerta).toHaveTextContent("Error del servidor");
    await user.click(within(alerta).getByRole("button", { name: "Reintentar" }));

    await waitFor(() => expect(filas()).toHaveLength(1));
  });
});
