import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, TimeoutError } from "@/features/shared/api/client";

import { getTenderAttachments } from "../services/tenderAttachmentsService";
import type { TenderAttachments } from "../types";

export type TenderAttachmentsState =
  | { status: "loading" }
  | { status: "ready"; data: TenderAttachments }
  | { status: "error"; message: string };

const FALLBACK_MESSAGE = "No se pudieron cargar los anexos de la licitación.";

function messageFrom(error: unknown): string {
  return error instanceof ApiError || error instanceof TimeoutError
    ? error.message
    : FALLBACK_MESSAGE;
}

export function useTenderAttachments(tenderId: string) {
  const [state, setState] = useState<TenderAttachmentsState>({ status: "loading" });
  const [reloadNonce, setReloadNonce] = useState(0);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  // `setState` solo dentro de los callbacks de la promesa, no en el cuerpo del efecto.
  useEffect(() => {
    let cancelled = false;
    getTenderAttachments(tenderId)
      .then((data) => {
        if (!cancelled) setState({ status: "ready", data });
      })
      .catch((error: unknown) => {
        if (!cancelled) setState({ status: "error", message: messageFrom(error) });
      });
    return () => {
      cancelled = true;
    };
  }, [tenderId, reloadNonce]);

  const reload = useCallback(() => {
    setState({ status: "loading" });
    setReloadNonce((n) => n + 1);
  }, []);

  /**
   * Vuelve a pedir la lista **sin** pasar por `loading`: tras subir o borrar un
   * archivo, la lista no puede parpadear ni perder lo que la persona ya veía. Un
   * error se ignora y se conserva la lista actual.
   */
  const refresh = useCallback(async (): Promise<void> => {
    try {
      const data = await getTenderAttachments(tenderId);
      if (mounted.current) setState({ status: "ready", data });
    } catch {
      // Se conserva la lista que ya había.
    }
  }, [tenderId]);

  return { state, reload, refresh };
}
