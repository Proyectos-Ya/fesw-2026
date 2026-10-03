"use client";

import { useId } from "react";

import { formatDateTime } from "@/features/matches/utils/format";
import { compraAgilFichaUrl } from "@/features/matches/utils/links";
import { Badge, type BadgeTone } from "@/features/shared/components/Badge";
import { Button } from "@/features/shared/components/Button";
import { Icon } from "@/features/shared/components/Icon";
import { useTenderAttachments } from "../hooks/useTenderAttachments";
import {
  ATTACHMENT_STATUS_LABELS,
  type AttachmentStatus,
  type OfficialAttachment,
} from "../types";

interface TenderAttachmentsPanelProps {
  tenderId: string;
  tenderCode: string;
}

/** La decisión 2 (subida de archivos) agrega los demás estados. */
const STATUS_TONE: Record<AttachmentStatus, BadgeTone> = { missing: "warning" };

/**
 * Lista oficial de anexos de la licitación (plan 233, decisión 1).
 *
 * Reemplaza a "Documentos asociados", que solo enlazaba a la ficha de Mercado
 * Público. Hoy solo informa qué documentos existen; los archivos no se guardan.
 */
export function TenderAttachmentsPanel({ tenderId, tenderCode }: TenderAttachmentsPanelProps) {
  const titleId = useId();
  const { state, reload } = useTenderAttachments(tenderId);

  return (
    <section
      aria-labelledby={titleId}
      className="mb-6 rounded-lg border border-border-subtle bg-surface-card p-6 shadow-xs"
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

      {state.status === "ready" && state.data.official.length > 0 && (
        <>
          <ul
            aria-label="Anexos oficiales"
            className="flex flex-col divide-y divide-border-subtle rounded-md border border-border-subtle"
          >
            {state.data.official.map((attachment) => (
              <AttachmentRow key={attachment.id} attachment={attachment} />
            ))}
          </ul>
          <p className="mt-2 text-xs text-text-subtle">
            Lista sincronizada con Mercado Público el {formatDateTime(state.data.list_synced_at)}.
          </p>
        </>
      )}

      {state.status === "ready" && state.data.official.length === 0 && (
        <p className="text-sm italic text-text-subtle">
          {state.data.list_synced_at === null
            ? "Todavía no tenemos la lista de anexos de esta licitación. Puedes revisarlos en Mercado Público."
            : "Mercado Público no informa anexos para esta licitación."}
        </p>
      )}

      {/* Si la lista falla o todavía no existe, la ficha oficial sigue siendo el
          camino a los documentos: el enlace se muestra en todos los estados. */}
      <a
        href={compraAgilFichaUrl(tenderCode)}
        target="_blank"
        rel="noreferrer noopener"
        className="mt-4 inline-flex items-center gap-2 rounded-md bg-primary-soft px-4 py-2 text-sm font-bold text-primary hover:bg-teal-100 transition-colors"
      >
        Ver documentos en Mercado Público
        <Icon name="external-link" size={14} />
      </a>
    </section>
  );
}

function AttachmentRow({ attachment }: { attachment: OfficialAttachment }) {
  return (
    <li className="flex items-center gap-3 p-3">
      <Icon name="file-text" size={16} color="var(--text-subtle)" />
      <span
        title={attachment.name}
        className="min-w-0 flex-1 truncate text-sm font-semibold text-text-strong"
      >
        {attachment.name}
      </span>
      {attachment.ext !== "" && <Badge tone="neutral">{attachment.ext.toUpperCase()}</Badge>}
      <Badge tone={STATUS_TONE[attachment.status]}>
        {ATTACHMENT_STATUS_LABELS[attachment.status]}
      </Badge>
    </li>
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
