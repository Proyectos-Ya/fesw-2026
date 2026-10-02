import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/features/shared/api/client";
import * as calendarService from "../../services/calendarService";
import { buildMilestone } from "../../test-utils";
import type { CalendarConnection } from "../../types";
import { consumeCalendarReturnTender, savePendingCalendarSync } from "../../utils/calendarReturn";
import { useCalendarSync } from "../useCalendarSync";

vi.mock("../../services/calendarService", () => ({
  getCalendarConnections: vi.fn(),
  startCalendarAuthorization: vi.fn(),
  syncMilestones: vi.fn(),
  disconnectCalendar: vi.fn(),
}));

const CON_HORA = buildMilestone({ id: "m-1", has_time: true });
const SIN_HORA = buildMilestone({ id: "m-2", has_time: false });
const CONECTADO = [{ provider: "google" as const, connected: true, account_email: "u@gmail.com", needs_reconnect: false }];
const DESCONECTADO = [{ provider: "google" as const, connected: false, account_email: null, needs_reconnect: false }];

function setup(conexiones: CalendarConnection[] = CONECTADO) {
  vi.mocked(calendarService.getCalendarConnections).mockResolvedValue(conexiones);
  const onSynced = vi.fn();
  const navigate = vi.fn();
  const hook = renderHook(() =>
    useCalendarSync({ tenderId: "t-1", milestones: [CON_HORA, SIN_HORA], onSynced, navigate }),
  );
  return { ...hook, onSynced, navigate };
}

describe("useCalendarSync", () => {
  beforeEach(() => {
    vi.mocked(calendarService.getCalendarConnections).mockReset();
    vi.mocked(calendarService.startCalendarAuthorization).mockReset();
    vi.mocked(calendarService.syncMilestones).mockReset();
    vi.mocked(calendarService.disconnectCalendar).mockReset();
    window.sessionStorage.clear();
  });

  it("carga el estado de la conexión", async () => {
    const { result } = setup();

    await waitFor(() => expect(result.current.connection?.account_email).toBe("u@gmail.com"));
    expect(result.current.available).toBe(true);
  });

  it("sin proveedores configurados la sincronización no está disponible", async () => {
    const { result } = setup([]);

    await waitFor(() => expect(result.current.loadingConnection).toBe(false));
    expect(result.current.available).toBe(false);
  });

  it("si hay hitos sin hora pide la hora antes de hacer nada", async () => {
    const { result } = setup();
    await waitFor(() => expect(result.current.connection).not.toBeNull());

    await act(async () => {
      await result.current.sync(["m-1", "m-2"]);
    });

    expect(result.current.state).toEqual({ status: "needsTime", milestoneIds: ["m-1", "m-2"], missingCount: 1 });
    expect(calendarService.syncMilestones).not.toHaveBeenCalled();
    expect(calendarService.startCalendarAuthorization).not.toHaveBeenCalled();
  });

  it("conectado, sincroniza con la hora confirmada y avisa el éxito", async () => {
    vi.mocked(calendarService.syncMilestones).mockResolvedValue({
      results: [
        { milestone_id: "m-1", synced: true },
        { milestone_id: "m-2", synced: true },
      ],
      failed_count: 0,
    });
    const { result, onSynced } = setup();
    await waitFor(() => expect(result.current.connection).not.toBeNull());
    await act(async () => {
      await result.current.sync(["m-1", "m-2"]);
    });

    await act(async () => {
      await result.current.confirmTime("08:30");
    });

    expect(calendarService.syncMilestones).toHaveBeenCalledWith("t-1", "google", ["m-1", "m-2"], "08:30");
    expect(result.current.state).toEqual({ status: "success", count: 2 });
    expect(onSynced).toHaveBeenCalled();
  });

  it("sin conexión redirige a Google recordando la licitación", async () => {
    vi.mocked(calendarService.startCalendarAuthorization).mockResolvedValue({
      authorization_url: "https://accounts.google.com/auth?state=x",
    });
    const { result, navigate } = setup(DESCONECTADO);
    await waitFor(() => expect(result.current.loadingConnection).toBe(false));

    await act(async () => {
      await result.current.sync(["m-1"]);
    });

    expect(calendarService.startCalendarAuthorization).toHaveBeenCalledWith("google", {
      tender_id: "t-1",
      milestone_ids: ["m-1"],
      default_time: null,
    });
    expect(navigate).toHaveBeenCalledWith("https://accounts.google.com/auth?state=x");
    expect(result.current.state).toEqual({ status: "redirecting" });
    expect(consumeCalendarReturnTender()).toBe("t-1");
  });

  it("si el backend dice que hay que reconectar, redirige a Google", async () => {
    vi.mocked(calendarService.syncMilestones).mockRejectedValue(new ApiError(409, "El acceso expiró."));
    vi.mocked(calendarService.startCalendarAuthorization).mockResolvedValue({ authorization_url: "https://g/auth" });
    const { result, navigate } = setup();
    await waitFor(() => expect(result.current.connection).not.toBeNull());

    await act(async () => {
      await result.current.sync(["m-1"]);
    });

    expect(navigate).toHaveBeenCalledWith("https://g/auth");
  });

  it("si algunos hitos fallan lo informa y reintenta solo esos", async () => {
    vi.mocked(calendarService.syncMilestones)
      .mockResolvedValueOnce({
        results: [
          { milestone_id: "m-1", synced: true },
          { milestone_id: "m-2", synced: false },
        ],
        failed_count: 1,
      })
      .mockResolvedValueOnce({ results: [{ milestone_id: "m-2", synced: true }], failed_count: 0 });
    const { result } = setup();
    await waitFor(() => expect(result.current.connection).not.toBeNull());
    await act(async () => {
      await result.current.sync(["m-1", "m-2"]);
    });
    await act(async () => {
      await result.current.confirmTime("09:00");
    });

    expect(result.current.state).toMatchObject({ status: "error", retryIds: ["m-2"], reconnect: false });
    if (result.current.state.status === "error") {
      expect(result.current.state.message).toMatch(/la sincronización no pudo completarse/i);
    }

    await act(async () => {
      await result.current.retry();
    });

    expect(calendarService.syncMilestones).toHaveBeenLastCalledWith("t-1", "google", ["m-2"], "09:00");
    expect(result.current.state).toEqual({ status: "success", count: 1 });
  });

  it("si Google no responde muestra el error y permite reintentar todo", async () => {
    vi.mocked(calendarService.syncMilestones).mockRejectedValue(
      new ApiError(502, "El servicio de calendario no respondió."),
    );
    const { result } = setup();
    await waitFor(() => expect(result.current.connection).not.toBeNull());

    await act(async () => {
      await result.current.sync(["m-1"]);
    });

    expect(result.current.state).toMatchObject({ status: "error", retryIds: ["m-1"] });
    if (result.current.state.status === "error") {
      expect(result.current.state.message).toMatch(/la sincronización no pudo completarse/i);
    }
  });

  it("al volver de Google completa la sincronización pendiente", async () => {
    savePendingCalendarSync({
      provider: "google",
      tender_id: "t-1",
      milestone_ids: ["m-2"],
      default_time: "09:00",
      account_email: "u@gmail.com",
    });
    vi.mocked(calendarService.syncMilestones).mockResolvedValue({
      results: [{ milestone_id: "m-2", synced: true }],
      failed_count: 0,
    });

    const { result } = setup();

    await waitFor(() => expect(result.current.state).toEqual({ status: "success", count: 1 }));
    expect(calendarService.syncMilestones).toHaveBeenCalledWith("t-1", "google", ["m-2"], "09:00");
  });

  it("desconectar revoca y actualiza el estado", async () => {
    vi.mocked(calendarService.disconnectCalendar).mockResolvedValue(undefined);
    const { result } = setup();
    await waitFor(() => expect(result.current.connection?.connected).toBe(true));

    await act(async () => {
      await result.current.disconnect();
    });

    expect(calendarService.disconnectCalendar).toHaveBeenCalledWith("google");
    expect(result.current.connection?.connected).toBe(false);
  });
});
