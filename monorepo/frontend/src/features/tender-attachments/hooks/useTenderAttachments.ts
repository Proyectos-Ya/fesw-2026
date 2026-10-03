import { useCallback, useEffect, useState } from "react";

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

  return { state, reload };
}
