"use client";

import { useEffect, useId, useState, type DragEvent } from "react";

import { compraAgilFichaUrl } from "@/features/matches/utils/links";
import { Button } from "@/features/shared/components/Button";
import { Icon } from "@/features/shared/components/Icon";
import { useAttachmentUploads } from "../hooks/useAttachmentUploads";
import { useProcessingPoll } from "../hooks/useProcessingPoll";
import { useTenderAttachments } from "../hooks/useTenderAttachments";
import type { OfficialAttachment } from "../types";
import { matchDroppedFiles } from "../utils/matchFiles";
import { AttachmentDropZone } from "./AttachmentDropZone";
import { AttachmentRow } from "./AttachmentRow";
import { DropRejectionAlert } from "./DropRejectionAlert";

interface TenderAttachmentsPanelProps {
  tenderId: string;
  tenderCode: string;
  onReadyKeyChange?: (readyKey: string) => void;
  onUploadSuccess?: () => void;
}

/** Tope de respaldo mientras la lista no carga; el real lo informa el backend. */
const DEFAULT_MAX_UPLOAD_BYTES = 50 * 1024 * 1024;

/**
 * Anexos de la licitación (plan 233).
 *
 * Muestra el buzón de arrastre y solo renderiza la lista de documentos una vez
 * que se activan subidas o existen archivos subidos por el usuario, sin mostrar
 * documentos faltantes ni nombres del catálogo de la API.
 */
export function TenderAttachmentsPanel({
  tenderId,
  tenderCode,
  onReadyKeyChange,
  onUploadSuccess,
}: TenderAttachmentsPanelProps) {
  const titleId = useId();
  const { state, reload, refresh } = useTenderAttachments(tenderId);
  const data = state.status === "ready" ? state.data : null;
  const uploads = useAttachmentUploads(tenderId, {
    maxSizeBytes: data?.max_upload_size_bytes ?? DEFAULT_MAX_UPLOAD_BYTES,
    onChanged: refresh,
  });
  const [dragging, setDragging] = useState(false);
  const [isProcessingFiles, setIsProcessingFiles] = useState(false);

  // Registro local de nombres reales de archivos subidos
  const [uploadedNames, setUploadedNames] = useState<Record<string, string>>(() => {
    if (typeof window === "undefined") return {};
    try {
      const saved = localStorage.getItem(`tender_uploaded_names_${tenderId}`);
      return saved ? JSON.parse(saved) : {};
    } catch {
      return {};
    }
  });

  const recordUploadedName = (attachmentId: string, name: string) => {
    setUploadedNames((prev) => {
      const updated = { ...prev, [attachmentId]: name };
      try {
        localStorage.setItem(`tender_uploaded_names_${tenderId}`, JSON.stringify(updated));
      } catch {}
      return updated;
    });
  };

  const removeUploadedName = (attachmentId: string) => {
    setUploadedNames((prev) => {
      const updated = { ...prev };
      delete updated[attachmentId];
      try {
        localStorage.setItem(`tender_uploaded_names_${tenderId}`, JSON.stringify(updated));
      } catch {}
      return updated;
    });
  };

  const official = data?.official ?? [];
  const canUpload = data?.can_upload === true;

  // Solo se renderizan las filas que tienen archivo subido o subida en curso
  const uploadedAttachments = official.filter(
    (a) => a.file !== null || uploads.rows[a.id] !== undefined,
  );

  const polling =
    data !== null &&
    data.processing_enabled === true &&
    uploadedAttachments.some((a) => a.processing === "processing");
  useProcessingPoll(Boolean(polling), refresh);

  const readyKey =
    uploadedAttachments
      .filter(
        (a) =>
          a.processing === "ready" ||
          (data?.processing_enabled === false && a.file !== null),
      )
      .map((a) => a.file?.id ?? a.id)
      .join(",") ?? "";

  useEffect(() => {
    onReadyKeyChange?.(readyKey);
  }, [readyKey, onReadyKeyChange]);

  const processingDisabled =
    data !== null &&
    data.processing_enabled === false &&
    uploadedAttachments.some((a) => a.processing === "processing");

  const handlePickFile = async (attachment: OfficialAttachment, file: File) => {
    if (isProcessingFiles) return;
    setIsProcessingFiles(true);
    try {
      recordUploadedName(attachment.id, file.name);
      await uploads.uploadFile(attachment, file);
      onUploadSuccess?.();
    } finally {
      setIsProcessingFiles(false);
    }
  };

  const handleDropFiles = async (files: File[]) => {
    if (files.length === 0 || isProcessingFiles) return;
    setIsProcessingFiles(true);
    try {
      const { matched } = matchDroppedFiles(files, official);
      for (const { attachment, file } of matched) {
        recordUploadedName(attachment.id, file.name);
      }
      await uploads.uploadDropped(files, official);
      onUploadSuccess?.();
    } finally {
      setIsProcessingFiles(false);
    }
  };

  const handleDeleteFile = (attachment: OfficialAttachment) => {
    removeUploadedName(attachment.id);
    void uploads.removeFile(attachment).then(() => {
      onUploadSuccess?.();
    });
  };

  function handleDragOver(event: DragEvent<HTMLElement>) {
    event.preventDefault();
    if (canUpload && !isProcessingFiles) setDragging(true);
  }

  function handleDragLeave(event: DragEvent<HTMLElement>) {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(false);
  }

  function handleDrop(event: DragEvent<HTMLElement>) {
    event.preventDefault();
    setDragging(false);
    if (!canUpload || isProcessingFiles) return;
    void handleDropFiles(Array.from(event.dataTransfer.files));
  }

  return (
    <section
      id="tender-attachments-panel"
      aria-labelledby={titleId}
      aria-busy={isProcessingFiles}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={`relative overflow-hidden mb-6 rounded-lg border border-border-subtle bg-surface-card p-6 shadow-xs ${
        dragging ? "ring-2 ring-primary/30" : ""
      }`}
    >
      <h2
        id={titleId}
        className="inline-flex items-center gap-2 text-sm font-bold text-text-strong"
      >
        <Icon name="paperclip" size={16} color="var(--primary)" />
        Anexos de la licitación
      </h2>
      <p className="mt-1 mb-3 text-sm text-text-muted">
        Documentos subidos para el análisis de la licitación.
      </p>

      {state.status === "loading" && (
        <p role="status" className="text-sm text-text-muted">
          Cargando anexos de la licitación…
        </p>
      )}

      {state.status === "error" && <ErrorAlert message={state.message} onRetry={reload} />}

      {isProcessingFiles && (
        <div
          role="status"
          aria-live="polite"
          data-testid="attachments-processing-loader"
          className="absolute inset-0 z-30 flex flex-col items-center justify-center gap-3 rounded-lg bg-surface-card/90 backdrop-blur-xs p-6 shadow-md transition-all"
        >
          <Icon name="loader-circle" size={40} className="animate-spin text-primary" />
          <div className="text-center">
            <p className="text-base font-semibold text-text-strong">Procesando archivos…</p>
            <p className="mt-1 text-xs text-text-muted">
              Por favor espera mientras preparamos y subimos tus documentos.
            </p>
          </div>
        </div>
      )}

      <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center">
        {canUpload && (
          <AttachmentDropZone
            onFiles={(files) => void handleDropFiles(files)}
            disabled={isProcessingFiles}
          />
        )}
        <a
          href={compraAgilFichaUrl(tenderCode)}
          target="_blank"
          rel="noreferrer noopener"
          className="inline-flex items-center gap-2 self-start rounded-md bg-primary-soft px-4 py-2 text-sm font-bold text-primary hover:bg-teal-100 transition-colors sm:self-center"
        >
          Ver documentos en Mercado Público
          <Icon name="external-link" size={14} />
        </a>
      </div>

      {canUpload && data?.quota != null && (
        <p className="mt-2 text-xs text-text-subtle">
          Subidas de anexos de tu empresa este mes: {data.quota.used} de {data.quota.limit}.
          {data.quota.used >= data.quota.limit && (
            <strong className="ml-1 font-semibold text-danger">
              Alcanzaste el tope de subidas de este mes.
            </strong>
          )}
        </p>
      )}

      {uploads.rejections.length > 0 && (
        <div className="mt-3">
          <DropRejectionAlert
            rejections={uploads.rejections}
            official={official}
            onClose={uploads.dismissRejections}
          />
        </div>
      )}

      {processingDisabled && (
        <p role="note" className="mt-3 text-xs text-text-muted">
          El resumen automático de anexos está desactivado en este entorno.
        </p>
      )}

      {uploadedAttachments.length > 0 && (
        <div className="mt-5">
          <ul
            aria-label="Documentos subidos"
            className="flex flex-col divide-y divide-border-subtle rounded-md border border-border-subtle"
          >
            {uploadedAttachments.map((attachment) => (
              <AttachmentRow
                key={attachment.id}
                attachment={attachment}
                displayName={
                  uploadedNames[attachment.id] ??
                  uploads.rows[attachment.id]?.file?.name ??
                  attachment.name
                }
                upload={uploads.rows[attachment.id]}
                canUpload={canUpload}
                disabled={isProcessingFiles}
                onPick={(file) => void handlePickFile(attachment, file)}
                onPickMultiple={(files) => void handleDropFiles(files)}
                onRetry={() => void uploads.retry(attachment)}
                onDelete={() => handleDeleteFile(attachment)}
              />
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function ErrorAlert({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div
      role="alert"
      className="flex flex-col gap-2 rounded-md border border-danger/20 bg-danger-soft/30 px-4 py-3 text-sm font-medium text-danger sm:flex-row sm:items-center sm:justify-between"
    >
      <span>{message}</span>
      <Button variant="ghost" onClick={onRetry} className="shrink-0">
        Reintentar
      </Button>
    </div>
  );
}
