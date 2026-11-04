import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, TimeoutError } from "@/features/shared/api/client";
import { getTenderDigest } from "../services/tenderDigestService";
import type { TenderDigest } from "../types";

export type TenderDigestState =
  | { status: "loading" }
  | { status: "ready"; data: TenderDigest }
  | { status: "error"; message: string };

const FALLBACK_MESSAGE = "No se pudo cargar el resumen de los anexos.";

function messageFrom(error: unknown): string {
  return error instanceof ApiError || error instanceof TimeoutError
    ? error.message
    : FALLBACK_MESSAGE;
}

export function useTenderDigest(
  tenderId: string,
  refreshKey: string
): { state: TenderDigestState; reload: () => void } {
  const [state, setState] = useState<TenderDigestState>({ status: "loading" });
  const [nonce, setNonce] = useState(0);
  const dataRef = useRef<TenderDigest | null>(null);

  useEffect(() => {
    let cancelled = false;

    // Solo si no tenemos datos previos pasamos por loading
    if (!dataRef.current) {
      setState({ status: "loading" });
    }

    getTenderDigest(tenderId)
      .then((data) => {
        if (!cancelled) {
          dataRef.current = data;
          setState({ status: "ready", data });
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          if (!dataRef.current) {
            setState({ status: "error", message: messageFrom(error) });
          }
        }
      });

    return () => {
      cancelled = true;
    };
  }, [tenderId, refreshKey, nonce]);

  const reload = useCallback(() => {
    dataRef.current = null;
    setState({ status: "loading" });
    setNonce((n) => n + 1);
  }, []);

  return { state, reload };
}
