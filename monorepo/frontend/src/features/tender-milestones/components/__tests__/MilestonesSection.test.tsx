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
  setMilestoneReminder: vi.fn(),
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
    vi.mocked(service.setMilestoneReminder).mockReset();
    vi.mocked(service.setMilestoneReminder).mockResolvedValue({
      milestone_id: "m-1",
      reminder_days_before: 3,
    });
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
    expect(visita.getByText("¡Vence en 2 días!")).toBeInTheDocument();
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

  it("marca los hitos ya sincronizados en cada calendario", async () => {
    vi.mocked(service.getTenderMilestones).mockResolvedValue(
      buildMilestoneList({ milestones: [buildMilestone({ synced_providers: ["google", "outlook"] })] }),
    );

    render(<MilestonesSection tenderId="t-1" now={AHORA} />);

    expect(await screen.findByText("En Google Calendar")).toBeInTheDocument();
    expect(screen.getByText("En Outlook Calendar")).toBeInTheDocument();
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
    expect(screen.getByText(/sube las bases en el asistente/i)).toBeInTheDocument();
  });

  it("con todas las bases ya leídas no deja volver a extraer y explica cómo releer una", async () => {
    // Volver a leer las mismas bases duplicaba o borraba hitos.
    vi.mocked(service.getTenderMilestones).mockResolvedValue(
      buildMilestoneList({ documents_count: 2, pending_documents_count: 0 }),
    );

    render(<MilestonesSection tenderId="t-1" now={AHORA} />);

    expect(await screen.findByRole("button", { name: /extraer hitos de las bases/i })).toBeDisabled();
    expect(screen.getByText(/ya se extrajeron los hitos de todas las bases subidas/i)).toBeInTheDocument();
  });

  it("con una base pendiente permite extraer", async () => {
    vi.mocked(service.getTenderMilestones).mockResolvedValue(
      buildMilestoneList({ documents_count: 2, pending_documents_count: 1 }),
    );

    render(<MilestonesSection tenderId="t-1" now={AHORA} />);

    expect(await screen.findByRole("button", { name: /extraer hitos de las bases/i })).toBeEnabled();
    expect(screen.queryByText(/ya se extrajeron los hitos/i)).not.toBeInTheDocument();
  });

  it("mientras la IA lee las bases recién subidas lo dice y no deja extraer a mano", async () => {
    vi.mocked(service.getTenderMilestones).mockResolvedValue(
      buildMilestoneList({ documents_count: 1, extraction_status: "running" }),
    );

    render(<MilestonesSection tenderId="t-1" now={AHORA} />);

    expect(await screen.findByText(/la ia está leyendo las bases que subiste/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /extraer hitos de las bases/i })).toBeDisabled();
  });

  it("si la extracción automática falló invita a reintentar con el botón", async () => {
    vi.mocked(service.getTenderMilestones).mockResolvedValue(
      buildMilestoneList({ documents_count: 1, pending_documents_count: 1, extraction_status: "failed" }),
    );

    render(<MilestonesSection tenderId="t-1" now={AHORA} />);

    expect(
      await screen.findByText(/no se pudieron extraer los hitos automáticamente/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /extraer hitos de las bases/i })).toBeEnabled();
  });

  it("extrae los hitos de las bases y muestra el resultado", async () => {
    const user = userEvent.setup();
    vi.mocked(service.getTenderMilestones).mockResolvedValue(
      buildMilestoneList({ documents_count: 1, pending_documents_count: 1 }),
    );
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
    vi.mocked(service.getTenderMilestones).mockResolvedValue(
      buildMilestoneList({ documents_count: 1, pending_documents_count: 1 }),
    );
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

  describe("sincronización con Outlook Calendar", () => {
    const AMBOS = [
      ...CONECTADO,
      { provider: "outlook" as const, connected: false, account_email: null, needs_reconnect: false },
    ];

    it("con los dos configurados ofrece sincronizar con cada uno", async () => {
      vi.mocked(calendarService.getCalendarConnections).mockResolvedValue(AMBOS);
      vi.mocked(service.getTenderMilestones).mockResolvedValue(buildMilestoneList());

      render(<MilestonesSection tenderId="t-1" now={AHORA} />);

      expect(await screen.findByRole("button", { name: /sincronizar con outlook calendar/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /sincronizar con google calendar/i })).toBeInTheDocument();
    });

    it("solo con Outlook configurado no ofrece Google", async () => {
      vi.mocked(calendarService.getCalendarConnections).mockResolvedValue([AMBOS[1]]);
      vi.mocked(service.getTenderMilestones).mockResolvedValue(buildMilestoneList());

      render(<MilestonesSection tenderId="t-1" now={AHORA} />);

      expect(await screen.findByRole("button", { name: /sincronizar con outlook calendar/i })).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /sincronizar con google calendar/i })).not.toBeInTheDocument();
      expect(screen.getByText(/te pediremos autorizar el acceso a tu Outlook Calendar/i)).toBeInTheDocument();
    });

    it("sincroniza los hitos elegidos con Outlook", async () => {
      const user = userEvent.setup();
      vi.mocked(calendarService.getCalendarConnections).mockResolvedValue([
        { provider: "outlook" as const, connected: true, account_email: "u@outlook.com", needs_reconnect: false },
      ]);
      vi.mocked(service.getTenderMilestones).mockResolvedValue(buildMilestoneList());
      vi.mocked(calendarService.syncMilestones).mockResolvedValue({
        results: [{ milestone_id: "m-1", synced: true }],
        failed_count: 0,
      });
      render(<MilestonesSection tenderId="t-1" now={AHORA} />);

      await user.click(await screen.findByRole("checkbox", { name: /cierre de recepción de ofertas/i }));
      await user.click(screen.getByRole("button", { name: /sincronizar con outlook calendar/i }));

      expect(await screen.findByText("1 hito sincronizado con Outlook Calendar.")).toBeInTheDocument();
      expect(calendarService.syncMilestones).toHaveBeenCalledWith("t-1", "outlook", ["m-1"], null);
    });
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

  describe("recordatorios por hito", () => {
    it("ofrece las anticipaciones y parte sin recordatorio", async () => {
      vi.mocked(service.getTenderMilestones).mockResolvedValue(buildMilestoneList());

      render(<MilestonesSection tenderId="t-1" now={AHORA} />);

      const selector = await screen.findByRole("combobox", {
        name: /recordatorio de cierre de recepción de ofertas/i,
      });
      expect(selector).toHaveValue("");
      expect(
        Array.from(selector.querySelectorAll("option")).map((o) => o.textContent),
      ).toEqual(["Sin recordatorio", "1 día antes", "3 días antes", "1 semana antes"]);
    });

    it("activa el recordatorio elegido y lo refleja en la fila", async () => {
      const user = userEvent.setup();
      vi.mocked(service.getTenderMilestones).mockResolvedValue(buildMilestoneList());

      render(<MilestonesSection tenderId="t-1" now={AHORA} />);
      const selector = await screen.findByRole("combobox", { name: /recordatorio de cierre/i });

      await user.selectOptions(selector, "3");

      await waitFor(() => expect(selector).toHaveValue("3"));
      expect(service.setMilestoneReminder).toHaveBeenCalledWith("t-1", "m-1", 3);
    });

    it("lo apaga volviendo a 'Sin recordatorio'", async () => {
      const user = userEvent.setup();
      vi.mocked(service.getTenderMilestones).mockResolvedValue(
        buildMilestoneList({ milestones: [buildMilestone({ reminder_days_before: 7 })] }),
      );
      vi.mocked(service.setMilestoneReminder).mockResolvedValue({
        milestone_id: "m-1",
        reminder_days_before: null,
      });

      render(<MilestonesSection tenderId="t-1" now={AHORA} />);
      const selector = await screen.findByRole("combobox", { name: /recordatorio de cierre/i });
      expect(selector).toHaveValue("7");

      await user.selectOptions(selector, "");

      await waitFor(() => expect(selector).toHaveValue(""));
      expect(service.setMilestoneReminder).toHaveBeenCalledWith("t-1", "m-1", null);
    });

    it("si el guardado falla vuelve al valor anterior y lo avisa", async () => {
      const user = userEvent.setup();
      vi.mocked(service.getTenderMilestones).mockResolvedValue(buildMilestoneList());
      vi.mocked(service.setMilestoneReminder).mockRejectedValue(
        new ApiError(500, "Error del servidor"),
      );

      render(<MilestonesSection tenderId="t-1" now={AHORA} />);
      const selector = await screen.findByRole("combobox", { name: /recordatorio de cierre/i });

      await user.selectOptions(selector, "1");

      expect(await screen.findByRole("alert")).toHaveTextContent(
        "No se pudo guardar el recordatorio.",
      );
      expect(selector).toHaveValue("");
    });

    it("un hito vencido ya no admite recordatorio", async () => {
      vi.mocked(service.getTenderMilestones).mockResolvedValue(
        buildMilestoneList({
          milestones: [buildMilestone({ urgency: "vencido", due_at: "2026-09-20T15:00:00Z" })],
        }),
      );

      render(<MilestonesSection tenderId="t-1" now={AHORA} />);

      await waitFor(() => expect(filas()).toHaveLength(1));
      expect(screen.queryByRole("combobox", { name: /recordatorio/i })).not.toBeInTheDocument();
    });
  });
});
