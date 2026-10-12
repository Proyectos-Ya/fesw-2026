"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { formatDateTime } from "@/features/matches/utils/format";
import { ApiError, TimeoutError, saveBlob } from "@/features/shared/api/client";
import { Button } from "@/features/shared/components/Button";
import { Icon } from "@/features/shared/components/Icon";

import { downloadExportFile, getExportJob } from "../services/exportService";
import { EXPORT_FORMAT_LABELS, type ExportJob } from "../types";

type ViewState =
  | { status: "loading" }
  | { status: "ready"; job: ExportJob }
  | { status: "not_found" }
  | { status: "error"; message: string };

const DEFAULT_POLL_MS = 5_000;

/**
 * La página del enlace que llega por correo cuando una exportación tardó más de
 * 10 s (HdU 19, criterios 8 y 9). Exige sesión: el archivo es de quien lo pidió.
 */
export function ExportDownloadView({
  jobId,
  pollIntervalMs = DEFAULT_POLL_MS,
}: {
  jobId: string;
  pollIntervalMs?: number;
}) {
  const [state, setState] = useState<ViewState>({ status: "loading" });
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    const consultar = async () => {
      try {
        const job = await getExportJob(jobId);
        if (cancelled) return;
        setState({ status: "ready", job });
        // Si abrió el correo antes de tiempo, se espera acá mismo.
        if (job.status === "processing") timer = setTimeout(() => void consultar(), pollIntervalMs);
      } catch (error: unknown) {
        if (cancelled) return;
        if (error instanceof ApiError && error.status === 404) {
          setState({ status: "not_found" });
        } else {
          setState({ status: "error", message: "No pudimos consultar la exportación." });
        }
      }
    };

    void consultar();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [jobId, pollIntervalMs]);

  const descargar = async () => {
    setDownloading(true);
    setDownloadError(null);
    try {
      const archivo = await downloadExportFile(jobId);
      saveBlob(archivo.blob, archivo.filename);
    } catch (error: unknown) {
      setDownloadError(
        error instanceof ApiError || error instanceof TimeoutError
          ? error.message
          : "No se pudo descargar el archivo.",
      );
    } finally {
      setDownloading(false);
    }
  };

  const volver = (
    <Link href="/matches" className="text-sm font-semibold text-primary hover:underline">
      Volver a mis licitaciones
    </Link>
  );

  if (state.status === "loading") {
    return (
      <p role="status" className="text-sm text-text-muted">
        Buscando tu archivo…
      </p>
    );
  }

  if (state.status === "not_found") {
    return (
      <section className="mx-auto max-w-lg space-y-3 text-center">
        <h1 className="font-display text-2xl font-bold text-text-strong">
          No encontramos esta exportación
        </h1>
        <p className="text-sm text-text-muted">
          Puede que sea de otra cuenta. Revisa que hayas iniciado sesión con el correo al que
          llegó el aviso.
        </p>
        {volver}
      </section>
    );
  }

  if (state.status === "error") {
    return (
      <section className="mx-auto max-w-lg space-y-3 text-center">
        <p role="alert" className="text-sm text-danger">
          {state.message}
        </p>
        {volver}
      </section>
    );
  }

  const { job } = state;
  const formato = EXPORT_FORMAT_LABELS[job.format];
  return (
    <section className="mx-auto max-w-lg space-y-4 rounded-lg border border-border-subtle bg-surface-card p-6">
      <div className="flex items-center gap-3">
        <span className="flex size-10 items-center justify-center rounded-md bg-primary-soft text-primary">
          <Icon name={job.format === "pdf" ? "file-text" : "file-spreadsheet"} size={20} />
        </span>
        <div>
          <h1 className="text-lg font-bold text-text-strong">Tu {formato} de la licitación</h1>
          <p className="font-mono text-xs text-text-subtle">{job.file_name}</p>
        </div>
      </div>

      {job.status === "processing" && (
        <p role="status" className="text-sm text-text-muted">
          Todavía se está generando. Esta página se actualiza sola.
        </p>
      )}

      {job.status === "failed" && (
        <p role="alert" className="text-sm text-danger">
          No se pudo generar el archivo. Vuelve a exportarlo desde la ficha de la licitación.
        </p>
      )}

      {job.status === "ready" && (
        <>
          <p className="text-sm text-text-muted">
            Disponible hasta el {formatDateTime(job.expires_at)}.
          </p>
          {downloadError && (
            <p role="alert" className="text-sm text-danger">
              {downloadError}
            </p>
          )}
          <Button type="button" onClick={() => void descargar()} isLoading={downloading}>
            <Icon name="download" size={15} />
            Descargar {formato}
          </Button>
        </>
      )}

      <div>{volver}</div>
    </section>
  );
}
