"use client";

import { useId, useState, type DragEvent } from "react";

import { formatDateTime } from "@/features/matches/utils/format";
import { compraAgilFichaUrl } from "@/features/matches/utils/links";
import { Button } from "@/features/shared/components/Button";
import { Icon } from "@/features/shared/components/Icon";
import { useAttachmentUploads } from "../hooks/useAttachmentUploads";
import { useProcessingPoll } from "../hooks/useProcessingPoll";
import { useTenderAttachments } from "../hooks/useTenderAttachments";
import { AttachmentDropZone } from "./AttachmentDropZone";
import { AttachmentRow } from "./AttachmentRow";
import { DigestCard } from "./DigestCard";
import { DropRejectionAlert } from "./DropRejectionAlert";

interface TenderAttachmentsPanelProps {
  tenderId: string;
  tenderCode: string;
}

/** Tope de respaldo mientras la lista no carga; el real lo informa el backend. */
const DEFAULT_MAX_UPLOAD_BYTES = 50 * 1024 * 1024;

/**
 * Anexos de la licitación (plan 233, decisiones 1 y 2).
 *
 * Reemplaza a "Documentos asociados", que solo enlazaba a la ficha de Mercado
 * Público. Lista los documentos oficiales y permite a la empresa subir cada uno
 * —arrastrándolos todos juntos o con el botón de su fila— una vez descargados
 * de Mercado Público. El backend valida que el archivo sea el anexo que dice ser.
 *
 * El asistente de la licitación (su drawer, `DocumentAttachmentManager`) sigue
 * con su propio adjuntar y no se toca acá.
 */
export function TenderAttachmentsPanel({ tenderId, tenderCode }: TenderAttachmentsPanelProps) {
  const titleId = useId();
  const { state, reload, refresh } = useTenderAttachments(tenderId);
  const data = state.status === "ready" ? state.data : null;
  const uploads = useAttachmentUploads(tenderId, {
    maxSizeBytes: data?.max_upload_size_bytes ?? DEFAULT_MAX_UPLOAD_BYTES,
    onChanged: refresh,
  });
  const [dragging, setDragging] = useState(false);

  const official = data?.official ?? [];
  const canUpload = data?.can_upload === true && official.length > 0;

  const polling =
    data !== null &&
    data.processing_enabled === true &&
    official.some((a) => a.processing === "processing");
  useProcessingPoll(Boolean(polling), refresh);

  const readyKey =
    data?.official
      .filter((a) => a.processing === "ready")
      .map((a) => a.file?.id ?? a.id)
      .join(",") ?? "";
  const processingDisabled =
    data !== null &&
    data.processing_enabled === false &&
    official.some((a) => a.processing === "processing");

  // Siempre se cancela el soltar por defecto: si no, el navegador abriría el
  // archivo en la pestaña y la persona perdería la ficha. Solo se actúa con permiso.
  function handleDragOver(event: DragEvent<HTMLElement>) {
    event.preventDefault();
    if (canUpload) setDragging(true);
  }

  function handleDragLeave(event: DragEvent<HTMLElement>) {
    // Pasar sobre un hijo también dispara `dragleave`: solo cuenta salir de la sección.
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(false);
  }

  function handleDrop(event: DragEvent<HTMLElement>) {
    event.preventDefault();
    setDragging(false);
    if (!canUpload) return;
    void uploads.uploadDropped(Array.from(event.dataTransfer.files), official);
  }

  return (
    <section
      id="tender-attachments-panel"
      aria-labelledby={titleId}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={`mb-6 rounded-lg border border-border-subtle bg-surface-card p-6 shadow-xs ${
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
        Lista oficial de documentos publicada en Mercado Público.
      </p>

      {state.status === "loading" && (
        <p role="status" className="text-sm text-text-muted">
          Cargando anexos de la licitación…
        </p>
      )}

      {state.status === "error" && <ErrorAlert message={state.message} onRetry={reload} />}

      {data !== null && data.official.length > 0 && (
        <>
          <ul
            aria-label="Anexos oficiales"
            className="flex flex-col divide-y divide-border-subtle rounded-md border border-border-subtle"
          >
            {data.official.map((attachment) => (
              <AttachmentRow
                key={attachment.id}
                attachment={attachment}
                upload={uploads.rows[attachment.id]}
                canUpload={data.can_upload}
                onPick={(file) => void uploads.uploadFile(attachment, file)}
                onRetry={() => void uploads.retry(attachment)}
                onDelete={() => void uploads.removeFile(attachment)}
              />
            ))}
          </ul>
          <p className="mt-2 text-xs text-text-subtle">
            Lista sincronizada con Mercado Público el {formatDateTime(data.list_synced_at)}.
          </p>
        </>
      )}

      {data !== null && data.official.length === 0 && (
        <p className="text-sm italic text-text-subtle">
          {data.list_synced_at === null
            ? "Todavía no tenemos la lista de anexos de esta licitación. Puedes revisarlos en Mercado Público."
            : "Mercado Público no informa anexos para esta licitación."}
        </p>
      )}

      {uploads.rejections.length > 0 && (
        <DropRejectionAlert
          rejections={uploads.rejections}
          official={official}
          onClose={uploads.dismissRejections}
        />
      )}

      {processingDisabled && (
        <p role="note" className="mt-3 text-xs text-text-muted">
          El resumen automático de anexos está desactivado en este entorno.
        </p>
      )}

      {readyKey !== "" && (
        <div className="mt-4">
          <DigestCard tenderId={tenderId} refreshKey={readyKey} />
        </div>
      )}

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

      {/* Si la lista falla o todavía no existe, la ficha oficial sigue siendo el
          camino a los documentos: el enlace se muestra en todos los estados. */}
      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        {canUpload && (
          <AttachmentDropZone
            onFiles={(files) => void uploads.uploadDropped(files, official)}
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
