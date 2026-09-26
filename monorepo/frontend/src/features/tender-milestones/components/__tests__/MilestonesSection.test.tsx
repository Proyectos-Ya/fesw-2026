import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/features/shared/api/client";
import * as calendarService from "../../services/calendarService";
import * as service from "../../services/milestonesService";
import { buildMilestone, buildMilestoneList } from "../../test-utils";
import { MilestonesSection } from "../MilestonesSection";

vi.mock("../../services/milestonesService", () => ({
  getTenderMilestones: vi.fn(),
  extractTenderMilestones: vi.fn(),
}));

vi.mock("../../services/calendarService", () => ({
  getCalendarConnections: vi.fn(),
  startCalendarAuthorization: vi.fn(),
  syncMilestones: vi.fn(),
  disconnectCalendar: vi.fn(),
}));

const AHORA = new Date("2026-10-01T15:00:00Z");
const CONECTADO = [
  { provider: "google" as const, connected: true, account_email: "u@gmail.com", needs_reconnect: false },
];

function filas() {
  return screen.getAllByRole("row").slice(1); // sin la cabecera
}

describe("MilestonesSection", () => {
  beforeEach(() => {
    vi.mocked(service.getTenderMilestones).mockReset();
    vi.mocked(service.extractTenderMilestones).mockReset();
    vi.mocked(calendarService.getCalendarConnections).mockReset();
    vi.mocked(calendarService.getCalendarConnections).mockResolvedValue([]);
    vi.mocked(calendarService.syncMilestones).mockReset();
    window.sessionStorage.clear();
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

  describe("sincronización con Google Calendar", () => {
    it("sin Google configurado no muestra el botón de sincronizar", async () => {
      vi.mocked(service.getTenderMilestones).mockResolvedValue(buildMilestoneList());

      render(<MilestonesSection tenderId="t-1" now={AHORA} />);

      await waitFor(() => expect(filas()).toHaveLength(1));
      await waitFor(() => expect(calendarService.getCalendarConnections).toHaveBeenCalled());
      expect(
        screen.queryByRole("button", { name: /sincronizar con google calendar/i }),
      ).not.toBeInTheDocument();
    });

    it("muestra la cuenta conectada y exige elegir hitos antes de sincronizar", async () => {
      vi.mocked(calendarService.getCalendarConnections).mockResolvedValue(CONECTADO);
      vi.mocked(service.getTenderMilestones).mockResolvedValue(buildMilestoneList());

      render(<MilestonesSection tenderId="t-1" now={AHORA} />);

      expect(await screen.findByText(/conectado como u@gmail.com/i)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /sincronizar con google calendar/i })).toBeDisabled();
    });

    it("sincroniza los hitos elegidos y los marca en la tabla", async () => {
      const user = userEvent.setup();
      vi.mocked(calendarService.getCalendarConnections).mockResolvedValue(CONECTADO);
      vi.mocked(service.getTenderMilestones)
        .mockResolvedValueOnce(buildMilestoneList())
        .mockResolvedValueOnce(
          buildMilestoneList({ milestones: [buildMilestone({ synced_providers: ["google"] })] }),
        );
      vi.mocked(calendarService.syncMilestones).mockResolvedValue({
        results: [{ milestone_id: "m-1", synced: true }],
        failed_count: 0,
      });
      render(<MilestonesSection tenderId="t-1" now={AHORA} />);
      await screen.findByText(/conectado como/i);

      await user.click(
        screen.getByRole("checkbox", { name: /seleccionar cierre de recepción de ofertas/i }),
      );
      await user.click(screen.getByRole("button", { name: /sincronizar con google calendar/i }));

      expect(await screen.findByText("1 hito sincronizado con Google Calendar.")).toBeInTheDocument();
      expect(calendarService.syncMilestones).toHaveBeenCalledWith("t-1", "google", ["m-1"], null);
      expect(await screen.findByText("En Google Calendar")).toBeInTheDocument();
    });

    it("antes de sincronizar un hito sin hora pide confirmar la hora", async () => {
      const user = userEvent.setup();
      vi.mocked(calendarService.getCalendarConnections).mockResolvedValue(CONECTADO);
      vi.mocked(service.getTenderMilestones).mockResolvedValue(
        buildMilestoneList({
          milestones: [buildMilestone({ has_time: false, due_at: "2026-10-20T03:00:00Z" })],
        }),
      );
      vi.mocked(calendarService.syncMilestones).mockResolvedValue({
        results: [{ milestone_id: "m-1", synced: true }],
        failed_count: 0,
      });
      render(<MilestonesSection tenderId="t-1" now={AHORA} />);
      await screen.findByText(/conectado como/i);

      await user.click(screen.getByRole("checkbox", { name: /seleccionar cierre/i }));
      await user.click(screen.getByRole("button", { name: /sincronizar con google calendar/i }));

      const dialogo = await screen.findByRole("dialog", { name: /confirma una hora/i });
      await user.click(within(dialogo).getByRole("button", { name: /confirmar y sincronizar/i }));

      await waitFor(() =>
        expect(calendarService.syncMilestones).toHaveBeenCalledWith("t-1", "google", ["m-1"], "09:00"),
      );
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    it("si la sincronización falla lo avisa y permite reintentar", async () => {
      const user = userEvent.setup();
      vi.mocked(calendarService.getCalendarConnections).mockResolvedValue(CONECTADO);
      vi.mocked(service.getTenderMilestones).mockResolvedValue(buildMilestoneList());
      vi.mocked(calendarService.syncMilestones)
        .mockRejectedValueOnce(new ApiError(502, "El servicio de calendario no respondió."))
        .mockResolvedValueOnce({ results: [{ milestone_id: "m-1", synced: true }], failed_count: 0 });
      render(<MilestonesSection tenderId="t-1" now={AHORA} />);
      await screen.findByText(/conectado como/i);

      await user.click(screen.getByRole("checkbox", { name: /seleccionar cierre/i }));
      await user.click(screen.getByRole("button", { name: /sincronizar con google calendar/i }));

      const alerta = await screen.findByRole("alert");
      expect(alerta).toHaveTextContent("La sincronización no pudo completarse.");
      await user.click(within(alerta).getByRole("button", { name: "Reintentar" }));

      expect(await screen.findByText("1 hito sincronizado con Google Calendar.")).toBeInTheDocument();
      expect(calendarService.syncMilestones).toHaveBeenCalledTimes(2);
    });

    it("seleccionar todos elige solo los hitos que no vencieron", async () => {
      const user = userEvent.setup();
      vi.mocked(calendarService.getCalendarConnections).mockResolvedValue(CONECTADO);
      vi.mocked(service.getTenderMilestones).mockResolvedValue(
        buildMilestoneList({
          milestones: [
            buildMilestone({
              id: "m-1",
              title: "Publicación",
              urgency: "vencido",
              due_at: "2026-09-20T15:00:00Z",
            }),
            buildMilestone({ id: "m-2", title: "Cierre" }),
          ],
        }),
      );
      render(<MilestonesSection tenderId="t-1" now={AHORA} />);
      await screen.findByText(/conectado como/i);

      await user.click(screen.getByRole("checkbox", { name: /seleccionar todos/i }));

      expect(screen.getByRole("checkbox", { name: "Seleccionar Publicación" })).not.toBeChecked();
      expect(screen.getByRole("checkbox", { name: "Seleccionar Cierre" })).toBeChecked();
    });
  });
});
