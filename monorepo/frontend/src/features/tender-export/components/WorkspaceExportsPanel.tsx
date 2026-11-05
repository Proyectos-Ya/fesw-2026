"use client";

import { useEffect, useState } from "react";

import { saveBlob, TimeoutError, ApiError } from "@/features/shared/api/client";
import { Icon } from "@/features/shared/components/Icon";

import { downloadExportFile, listWorkspaceExports } from "../services/exportService";
import { EXPORT_FORMAT_LABELS, type ExportJob, type ExportJobStatus } from "../types";

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString("es-CL", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

const STATUS_LABELS: Record<ExportJobStatus, string> = {
  processing: "Generando…",
  ready: "Listo",
  failed: "Falló",
};

const STATUS_COLORS: Record<ExportJobStatus, string> = {
  processing: "text-text-subtle",
  ready: "text-success",
  failed: "text-danger",
};

export function WorkspaceExportsPanel() {
  const [jobs, setJobs] = useState<ExportJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listWorkspaceExports()
      .then((data) => { if (!cancelled) setJobs(data); })
      .catch(() => { if (!cancelled) setError("No se pudieron cargar los documentos."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const handleDownload = async (job: ExportJob) => {
    setDownloadingId(job.id);
    setDownloadError(null);
    try {
      const archivo = await downloadExportFile(job.id);
      saveBlob(archivo.blob, archivo.filename);
    } catch (err: unknown) {
      setDownloadError(
        err instanceof ApiError || err instanceof TimeoutError
          ? err.message
          : "No se pudo descargar el archivo.",
      );
    } finally {
      setDownloadingId(null);
    }
  };

  if (loading) {
    return (
      <p className="text-sm text-text-subtle py-4">Cargando documentos del equipo…</p>
    );
  }

  if (error) {
    return <p className="text-sm text-danger py-4">{error}</p>;
  }

  if (jobs.length === 0) {
    return (
      <p className="text-sm text-text-subtle py-4">
        Todavía no hay documentos generados en este espacio de trabajo.
      </p>
    );
  }

  return (
    <div className="space-y-1">
      {downloadError && (
        <p role="alert" className="text-xs text-danger mb-2">{downloadError}</p>
      )}
      <ul className="divide-y divide-border-subtle">
        {jobs.map((job) => (
          <li key={job.id} className="flex items-center gap-3 py-3">
            <span className="flex size-8 items-center justify-center rounded-md bg-surface-subtle text-text-subtle flex-none">
              <Icon name={job.format === "pdf" ? "file-text" : "file-spreadsheet"} size={16} />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-text-strong truncate">{job.file_name}</p>
              <p className="text-xs text-text-subtle mt-0.5">
                {EXPORT_FORMAT_LABELS[job.format]} · {formatDate(job.created_at)}
              </p>
            </div>
            <span className={`text-xs font-medium ${STATUS_COLORS[job.status]} flex-none`}>
              {STATUS_LABELS[job.status]}
            </span>
            {job.status === "ready" && (
              <button
                type="button"
                onClick={() => void handleDownload(job)}
                disabled={downloadingId === job.id}
                aria-label={`Descargar ${job.file_name}`}
                className="flex-none p-1 text-text-subtle hover:text-primary rounded-md hover:bg-surface-hover transition-colors disabled:opacity-50"
              >
                <Icon name={downloadingId === job.id ? "loader-circle" : "download"} size={15} />
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
