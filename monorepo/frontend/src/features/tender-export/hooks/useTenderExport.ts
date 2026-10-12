import { useCallback, useEffect, useState } from "react";

import { ApiError, TimeoutError, saveBlob } from "@/features/shared/api/client";

import { downloadExportFile, exportTender, getExportJob } from "../services/exportService";
import type { ExportFormat, ExportSection } from "../types";

export type ExportState =
  | { status: "idle" }
  | { status: "generating"; format: ExportFormat }
  /** Pasó a segundo plano (criterios 8 y 9): se consulta hasta que termine. */
  | { status: "queued"; format: ExportFormat; message: string }
  | { status: "done"; format: ExportFormat }
  | { status: "error"; message: string };

const DEFAULT_POLL_MS = 5_000;

function messageFrom(error: unknown, fallback: string): string {
  return error instanceof ApiError || error instanceof TimeoutError ? error.message : fallback;
}

export function useTenderExport(
  tenderId: string,
  { pollIntervalMs = DEFAULT_POLL_MS }: { pollIntervalMs?: number } = {},
) {
  const [state, setState] = useState<ExportState>({ status: "idle" });
  const [queuedJobId, setQueuedJobId] = useState<string | null>(null);

  const exportAs = useCallback(
    async (format: ExportFormat, sections: readonly ExportSection[]) => {
      setState({ status: "generating", format });
      setQueuedJobId(null);
      try {
        const resultado = await exportTender(tenderId, format, sections);
        if (resultado.kind === "file") {
          saveBlob(resultado.blob, resultado.filename);
          setState({ status: "done", format });
        } else {
          setState({ status: "queued", format, message: resultado.message });
          setQueuedJobId(resultado.jobId);
        }
      } catch (error: unknown) {
        setState({ status: "error", message: messageFrom(error, "No se pudo generar el archivo.") });
      }
    },
    [tenderId],
  );

  // Mientras la página siga abierta, se descarga solo al terminar. Si el
  // usuario se va, el correo le lleva el enlace.
  useEffect(() => {
    if (queuedJobId === null) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    const consultar = async () => {
      try {
        const job = await getExportJob(queuedJobId);
        if (cancelled) return;
        if (job.status === "ready") {
          const archivo = await downloadExportFile(queuedJobId);
          if (cancelled) return;
          saveBlob(archivo.blob, archivo.filename);
          setState({ status: "done", format: job.format });
          setQueuedJobId(null);
          return;
        }
        if (job.status === "failed") {
          setState({
            status: "error",
            message: "No se pudo generar el archivo. Vuelve a intentarlo.",
          });
          setQueuedJobId(null);
          return;
        }
      } catch {
        // Un corte de red no cancela la espera: el archivo sigue generándose.
      }
      if (!cancelled) timer = setTimeout(() => void consultar(), pollIntervalMs);
    };

    timer = setTimeout(() => void consultar(), pollIntervalMs);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [queuedJobId, pollIntervalMs]);

  return { state, exportAs };
}
