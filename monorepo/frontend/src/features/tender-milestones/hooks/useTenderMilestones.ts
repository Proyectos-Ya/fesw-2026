import { useCallback, useEffect, useState } from "react";

import { ApiError, TimeoutError } from "@/features/shared/api/client";

import { extractTenderMilestones, getTenderMilestones } from "../services/milestonesService";
import type { MilestoneList } from "../types";

export type MilestonesState =
  | { status: "loading" }
  | { status: "ready"; data: MilestoneList }
  | { status: "error"; message: string };

function messageFrom(error: unknown, fallback: string): string {
  return error instanceof ApiError || error instanceof TimeoutError ? error.message : fallback;
}

function discardedNotice(count: number): string | null {
  if (count === 0) return null;
  if (count === 1) return "1 fecha no se pudo interpretar y se omitió.";
  return `${count} fechas no se pudieron interpretar y se omitieron.`;
}

export function useTenderMilestones(tenderId: string) {
  const [state, setState] = useState<MilestonesState>({ status: "loading" });
  const [reloadNonce, setReloadNonce] = useState(0);
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractError, setExtractError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getTenderMilestones(tenderId)
      .then((data) => {
        if (!cancelled) setState({ status: "ready", data });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            status: "error",
            message: messageFrom(error, "No se pudieron cargar los hitos de la licitación."),
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [tenderId, reloadNonce]);

  const reload = useCallback(() => {
    setState({ status: "loading" });
    setReloadNonce((n) => n + 1);
  }, []);

  const extract = useCallback(async () => {
    setIsExtracting(true);
    setExtractError(null);
    setNotice(null);
    try {
      const data = await extractTenderMilestones(tenderId);
      setState({ status: "ready", data });
      setNotice(discardedNotice(data.discarded_count));
    } catch (error: unknown) {
      setExtractError(messageFrom(error, "No se pudieron extraer los hitos de las bases."));
    } finally {
      setIsExtracting(false);
    }
  }, [tenderId]);

  return { state, reload, extract, isExtracting, extractError, notice };
}
