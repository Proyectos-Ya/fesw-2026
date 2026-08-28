"use client";

/* eslint-disable react-hooks/set-state-in-effect -- la carga inicial usa el patrón canónico de efecto + flag de cancelación, igual que el resto de la app. */

import { useCallback, useEffect, useState } from "react";
import { ApiError, TimeoutError } from "@/features/shared/api/client";
import type { NotificationItem } from "../notificationTypes";
import {
  getNotifications,
  getUnreadCount,
  markAllNotificationsRead,
  markNotificationRead,
} from "../services/notificationService";

export type NotificationsState =
  | { kind: "loading" }
  | { kind: "ready"; items: NotificationItem[] }
  | { kind: "error"; message: string };

/** Cada cuánto se refresca el contador de la campanita, en milisegundos. */
const POLL_INTERVAL_MS = 60_000;

function mensajeDeError(err: unknown): string {
  if (err instanceof ApiError || err instanceof TimeoutError) return err.message;
  return "No pudimos cargar tus alertas.";
}

export function useNotifications(onlyUnread = false) {
  const [state, setState] = useState<NotificationsState>({ kind: "loading" });
  const [retryNonce, setRetryNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setState({ kind: "loading" });

    void (async () => {
      try {
        const items = await getNotifications(onlyUnread);
        if (!cancelled) setState({ kind: "ready", items });
      } catch (err) {
        if (!cancelled) setState({ kind: "error", message: mensajeDeError(err) });
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [onlyUnread, retryNonce]);

  const retry = useCallback(() => setRetryNonce((n) => n + 1), []);

  const markRead = useCallback(async (notificationId: string) => {
    // Optimista: el panel se marca al instante y, si la petición falla, se
    // deshace. Esperar la respuesta haría que el aviso siguiera en negrita
    // mientras el usuario ya navegó a la licitación.
    let previo: NotificationItem[] = [];
    setState((actual) => {
      if (actual.kind !== "ready") return actual;
      previo = actual.items;
      return {
        kind: "ready",
        items: actual.items.map((item) =>
          item.id === notificationId && item.read_at === null
            ? { ...item, read_at: new Date().toISOString() }
            : item,
        ),
      };
    });

    try {
      await markNotificationRead(notificationId);
    } catch {
      setState((actual) =>
        actual.kind === "ready" ? { kind: "ready", items: previo } : actual,
      );
    }
  }, []);

  const markAllRead = useCallback(async () => {
    let previo: NotificationItem[] = [];
    const ahora = new Date().toISOString();
    setState((actual) => {
      if (actual.kind !== "ready") return actual;
      previo = actual.items;
      return {
        kind: "ready",
        items: actual.items.map((item) =>
          item.read_at === null ? { ...item, read_at: ahora } : item,
        ),
      };
    });

    try {
      await markAllNotificationsRead();
    } catch {
      setState((actual) =>
        actual.kind === "ready" ? { kind: "ready", items: previo } : actual,
      );
    }
  }, []);

  return { state, retry, markRead, markAllRead };
}

/**
 * Contador de avisos sin leer, con refresco periódico.
 *
 * Un fallo del sondeo no rompe nada visible: el badge simplemente se queda con
 * el último valor conocido.
 */
export function useUnreadCount() {
  const [count, setCount] = useState(0);

  useEffect(() => {
    let cancelled = false;

    const refrescar = async () => {
      try {
        const { count: nuevo } = await getUnreadCount();
        if (!cancelled) setCount(nuevo);
      } catch {
        // Silencio deliberado: es un refresco de fondo.
      }
    };

    void refrescar();
    const id = setInterval(() => void refrescar(), POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return count;
}
