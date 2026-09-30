import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, TimeoutError } from "@/features/shared/api/client";

import {
  disconnectCalendar,
  getCalendarConnections,
  startCalendarAuthorization,
  syncMilestones,
} from "../services/calendarService";
import type { CalendarConnection, CalendarProvider, TenderMilestone } from "../types";
import {
  consumePendingCalendarSync,
  rememberCalendarReturnTender,
} from "../utils/calendarReturn";

export type CalendarSyncState =
  | { status: "idle" }
  | { status: "needsTime"; milestoneIds: string[]; missingCount: number }
  | { status: "redirecting" }
  | { status: "syncing" }
  | { status: "success"; count: number }
  | { status: "error"; message: string; retryIds: string[]; reconnect: boolean };

interface UseCalendarSyncOptions {
  tenderId: string;
  milestones: TenderMilestone[];
  /** Se llama cuando al menos un hito quedó en el calendario, para refrescar la tabla. */
  onSynced: () => void;
  navigate?: (url: string) => void;
  provider?: CalendarProvider;
}

const SYNC_FAILED = "La sincronización no pudo completarse.";

function errorDetail(error: unknown): string {
  return error instanceof ApiError || error instanceof TimeoutError ? error.message : "";
}

function defaultNavigate(url: string): void {
  window.location.assign(url);
}

export function useCalendarSync({
  tenderId,
  milestones,
  onSynced,
  navigate = defaultNavigate,
  provider = "google",
}: UseCalendarSyncOptions) {
  const [state, setState] = useState<CalendarSyncState>({ status: "idle" });
  const [connection, setConnection] = useState<CalendarConnection | null>(null);
  const [available, setAvailable] = useState(false);
  const [loadingConnection, setLoadingConnection] = useState(true);
  const lastTime = useRef<string | null>(null);
  const pendingHandled = useRef(false);

  useEffect(() => {
    let cancelled = false;
    getCalendarConnections()
      .then((connections) => {
        if (cancelled) return;
        const found = connections.find((c) => c.provider === provider) ?? null;
        setConnection(found);
        setAvailable(found !== null);
      })
      .catch(() => {
        if (!cancelled) setAvailable(false);
      })
      .finally(() => {
        if (!cancelled) setLoadingConnection(false);
      });
    return () => {
      cancelled = true;
    };
  }, [provider]);

  const authorize = useCallback(
    async (ids: string[], time: string | null) => {
      setState({ status: "redirecting" });
      rememberCalendarReturnTender(tenderId);
      try {
        const { authorization_url } = await startCalendarAuthorization(provider, {
          tender_id: tenderId,
          milestone_ids: ids,
          default_time: time,
        });
        navigate(authorization_url);
      } catch (error: unknown) {
        setState({
          status: "error",
          message: errorDetail(error) || "No se pudo iniciar la conexión con Google Calendar.",
          retryIds: ids,
          reconnect: true,
        });
      }
    },
    [navigate, provider, tenderId],
  );

  const run = useCallback(
    async (ids: string[], time: string | null) => {
      lastTime.current = time;
      setState({ status: "syncing" });
      try {
        const response = await syncMilestones(tenderId, provider, ids, time);
        const failed = response.results.filter((r) => !r.synced).map((r) => r.milestone_id);
        const syncedCount = response.results.length - failed.length;
        if (syncedCount > 0) onSynced();
        if (failed.length > 0) {
          setState({
            status: "error",
            message: `${SYNC_FAILED} ${failed.length} de ${ids.length} hitos no se enviaron a Google Calendar.`,
            retryIds: failed,
            reconnect: false,
          });
          return;
        }
        setState({ status: "success", count: syncedCount });
        setConnection((c) => (c ? { ...c, connected: true, needs_reconnect: false } : c));
      } catch (error: unknown) {
        if (error instanceof ApiError && error.status === 409) {
          await authorize(ids, time);
          return;
        }
        const detail = errorDetail(error);
        setState({
          status: "error",
          message: detail ? `${SYNC_FAILED} ${detail}` : SYNC_FAILED,
          retryIds: ids,
          reconnect: false,
        });
      }
    },
    [authorize, onSynced, provider, tenderId],
  );

  // Al volver de Google: completa lo que el usuario había pedido sincronizar.
  useEffect(() => {
    if (pendingHandled.current) return;
    pendingHandled.current = true;
    const pending = consumePendingCalendarSync(tenderId);
    // Sincroniza contra el backend al montar, como la carga inicial de useTenderDocuments.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (pending) void run(pending.milestone_ids, pending.default_time);
  }, [run, tenderId]);

  const sync = useCallback(
    async (ids: string[], time?: string) => {
      const missing = milestones.filter((m) => ids.includes(m.id) && !m.has_time);
      if (missing.length > 0 && time === undefined) {
        setState({ status: "needsTime", milestoneIds: ids, missingCount: missing.length });
        return;
      }
      const effectiveTime = time ?? null;
      if (!connection?.connected) {
        await authorize(ids, effectiveTime);
        return;
      }
      await run(ids, effectiveTime);
    },
    [authorize, connection, milestones, run],
  );

  const confirmTime = useCallback(
    async (time: string) => {
      if (state.status !== "needsTime") return;
      await sync(state.milestoneIds, time);
    },
    [state, sync],
  );

  const cancelTime = useCallback(() => setState({ status: "idle" }), []);

  const retry = useCallback(async () => {
    if (state.status !== "error") return;
    if (state.reconnect) {
      await authorize(state.retryIds, lastTime.current);
      return;
    }
    await run(state.retryIds, lastTime.current);
  }, [authorize, run, state]);

  const disconnect = useCallback(async () => {
    try {
      await disconnectCalendar(provider);
      setConnection((c) => (c ? { ...c, connected: false, account_email: null, needs_reconnect: false } : c));
      setState({ status: "idle" });
    } catch (error: unknown) {
      setState({
        status: "error",
        message: errorDetail(error) || "No se pudo desconectar Google Calendar.",
        retryIds: [],
        reconnect: false,
      });
    }
  }, [provider]);

  return {
    state,
    connection,
    available,
    loadingConnection,
    sync,
    confirmTime,
    cancelTime,
    retry,
    disconnect,
  };
}
