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

function unavailableNotice(count: number): string | null {
  if (count === 0) return null;
  if (count === 1) {
    return "1 documento que subiste ya no está disponible. Vuelve a adjuntarlo en el asistente para extraer sus hitos.";
  }
  return `${count} documentos que subiste ya no están disponibles. Vuelve a adjuntarlos en el asistente para extraer sus hitos.`;
}

/** Lo que conviene contarle al usuario después de extraer, o `null` si nada. */
function extractionNotice(data: MilestoneList): string | null {
  // Si la IA leyó bases y no salió ningún hito de ella, la tabla queda igual
  // que antes de extraer; sin este aviso eso parece un error.
  const noneFound =
    data.documents_count > 0 && !data.milestones.some((m) => m.source === "ia_documento")
      ? "La IA no encontró plazos en las bases adjuntas."
      : null;
  const avisos = [
    discardedNotice(data.discarded_count),
    unavailableNotice(data.unavailable_documents_count),
    noneFound,
  ].filter((aviso): aviso is string => aviso !== null);
  return avisos.length > 0 ? avisos.join(" ") : null;
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

  /** Recarga sin pasar por "cargando": la tabla sigue visible mientras tanto. */
  const refresh = useCallback(async () => {
    try {
      const data = await getTenderMilestones(tenderId);
      setState({ status: "ready", data });
    } catch {
      // Se conserva la tabla anterior; la próxima carga completa mostrará el error.
    }
  }, [tenderId]);

  const extract = useCallback(async () => {
    setIsExtracting(true);
    setExtractError(null);
    setNotice(null);
    try {
      const data = await extractTenderMilestones(tenderId);
      setState({ status: "ready", data });
      setNotice(extractionNotice(data));
    } catch (error: unknown) {
      setExtractError(messageFrom(error, "No se pudieron extraer los hitos de las bases."));
    } finally {
      setIsExtracting(false);
    }
  }, [tenderId]);

  return { state, reload, refresh, extract, isExtracting, extractError, notice };
}
