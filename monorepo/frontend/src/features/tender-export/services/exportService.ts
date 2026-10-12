import { apiDownloadOrAccepted, apiFetch } from "@/features/shared/api/client";

import type {
  DownloadedFile,
  ExportFormat,
  ExportJob,
  ExportResult,
  ExportSection,
} from "../types";

interface QueuedBody {
  job_id: string;
  message: string;
}

function isQueuedBody(body: unknown): body is QueuedBody {
  if (!body || typeof body !== "object") return false;
  const campos = body as Record<string, unknown>;
  return typeof campos.job_id === "string" && typeof campos.message === "string";
}

export async function exportTender(
  tenderId: string,
  format: ExportFormat,
  sections: readonly ExportSection[],
): Promise<ExportResult> {
  const resultado = await apiDownloadOrAccepted(`/tenders/${encodeURIComponent(tenderId)}/exports`, {
    method: "POST",
    body: JSON.stringify({ format, sections }),
  });

  if (resultado.kind === "accepted") {
    if (!isQueuedBody(resultado.body)) {
      throw new Error("La respuesta de la exportación no tiene el formato esperado.");
    }
    return { kind: "queued", jobId: resultado.body.job_id, message: resultado.body.message };
  }
  return {
    kind: "file",
    blob: resultado.blob,
    filename: resultado.filename ?? `licitacion.${format}`,
  };
}

export function getExportJob(jobId: string): Promise<ExportJob> {
  return apiFetch<ExportJob>(`/exports/${encodeURIComponent(jobId)}`);
}

export async function downloadExportFile(jobId: string): Promise<DownloadedFile> {
  const resultado = await apiDownloadOrAccepted(`/exports/${encodeURIComponent(jobId)}/file`);
  if (resultado.kind !== "file") {
    throw new Error("El archivo todavía no está disponible.");
  }
  return { blob: resultado.blob, filename: resultado.filename ?? "licitacion" };
}
