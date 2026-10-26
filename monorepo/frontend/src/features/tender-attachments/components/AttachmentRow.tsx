"use client";

import { useRef, useState, type DragEvent } from "react";

import { Badge, type BadgeTone } from "@/features/shared/components/Badge";
import { Button } from "@/features/shared/components/Button";
import { Icon } from "@/features/shared/components/Icon";
import type { RowUpload } from "../hooks/useAttachmentUploads";
import {
  ATTACHMENT_STATUS_LABELS,
  STATUS_REASON_FALLBACK,
  STATUS_REASON_LABELS,
  VISIBILITY_LABELS,
  type AttachmentStatus,
  type OfficialAttachment,
} from "../types";
import { formatFileSize } from "../utils/formatFileSize";
import { VISIBILITY_HINTS, sharingNotice } from "../utils/sharing";
import { ProcessingBadge } from "./ProcessingBadge";

const STATUS_TONE: Record<AttachmentStatus, BadgeTone> = {
  missing: "warning",
  uploading: "info",
  stored: "success",
  rejected: "danger",
  unsupported: "neutral",
};

interface AttachmentRowProps {
  attachment: OfficialAttachment;
  displayName?: string;
  /** Lo que pasa localmente con la fila (subiendo, borrando, error); `undefined` = nada. */
  upload?: RowUpload;
  canUpload: boolean;
  disabled?: boolean;
  onPick: (file: File) => void;
  onPickMultiple?: (files: File[]) => void;
  onRetry: () => void;
  onDelete: () => void;
}

const BUSY_LABEL: Partial<Record<RowUpload["phase"], string>> = {
  queued: "En cola",
  hashing: "Preparando…",
  requesting: "Preparando…",
  verifying: "Verificando…",
  deleting: "Borrando…",
};

/** Un anexo oficial con su estado, el archivo que la empresa subió y las acciones de la fila. */
export function AttachmentRow({
  attachment,
  displayName,
  upload,
  canUpload,
  disabled = false,
  onPick,
  onPickMultiple,
  onRetry,
  onDelete,
}: AttachmentRowProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const failed = upload?.phase === "error";
  const busy = upload !== undefined && !failed;
  const file = attachment.file;
  const percent = Math.round((upload?.progress ?? 0) * 100);
  const notice = sharingNotice(attachment.file);

  const [isDragOver, setIsDragOver] = useState(false);

  const canPick =
    canUpload &&
    !busy &&
    !disabled &&
    (failed ||
      attachment.status === "missing" ||
      attachment.status === "uploading" ||
      attachment.status === "rejected");
  const canDelete =
    canUpload && !busy && !disabled && file !== null && file.is_mine && file.visibility === "private";

  function handleDragOver(event: DragEvent<HTMLLIElement>) {
    if (!canPick || disabled) return;
    event.preventDefault();
    event.stopPropagation();
    event.dataTransfer.dropEffect = "copy";
    setIsDragOver(true);
  }

  function handleDragLeave(event: DragEvent<HTMLLIElement>) {
    event.preventDefault();
    event.stopPropagation();
    setIsDragOver(false);
  }

  function handleDrop(event: DragEvent<HTMLLIElement>) {
    event.preventDefault();
    event.stopPropagation();
    setIsDragOver(false);
    if (!canPick || disabled) return;
    const droppedFiles = Array.from(event.dataTransfer.files ?? []);
    if (droppedFiles.length === 1) {
      onPick(droppedFiles[0]);
    } else if (droppedFiles.length > 1) {
      if (onPickMultiple) {
        onPickMultiple(droppedFiles);
      } else {
        onPick(droppedFiles[0]);
      }
    }
  }

  return (
    <li
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={`flex flex-col gap-2 p-3 transition-colors ${
        isDragOver ? "rounded-md bg-primary/10 ring-2 ring-primary ring-inset" : ""
      }`}
    >
      <div className="flex flex-wrap items-center gap-3">
        <Icon name="file-text" size={16} color="var(--text-subtle)" />
        {(() => {
          const nombreVisible = displayName ?? attachment.name;
          const extensionVisible = nombreVisible.includes(".")
            ? nombreVisible.split(".").pop()?.trim() || ""
            : attachment.ext;
          return (
            <>
              <span
                title={nombreVisible}
                className="min-w-0 flex-1 truncate text-sm font-semibold text-text-strong"
              >
                {nombreVisible}
              </span>
              {extensionVisible !== "" && (
                <Badge tone="neutral">{extensionVisible.toUpperCase()}</Badge>
              )}
            </>
          );
        })()}

        {upload === undefined && (
          <>
            <Badge tone={STATUS_TONE[attachment.status]}>
              {ATTACHMENT_STATUS_LABELS[attachment.status]}
            </Badge>
            <ProcessingBadge processing={attachment.processing} />
          </>
        )}
        {failed && (
          <Badge tone="danger" iconLeft={<Icon name="circle-alert" size={12} />}>
            Error
          </Badge>
        )}
        {busy && upload.phase === "uploading" && (
          <Badge tone="info" iconLeft={<Icon name="loader-circle" size={12} className="animate-spin" />}>
            Subiendo {percent} %
          </Badge>
        )}
        {busy && upload.phase !== "uploading" && (
          <Badge tone="info" iconLeft={<Icon name="loader-circle" size={12} className="animate-spin" />}>
            {BUSY_LABEL[upload.phase]}
          </Badge>
        )}

        {file !== null && upload === undefined && (
          <span className="inline-flex items-center gap-1.5 text-xs text-text-subtle">
            <span>{formatFileSize(file.size_bytes)}</span>
            <span aria-hidden="true">·</span>
            <Badge
              tone={file.visibility === "shared" ? "teal" : "neutral"}
              iconLeft={<Icon name={file.visibility === "shared" ? "users" : "lock"} size={12} />}
            >
              <span title={VISIBILITY_HINTS[file.visibility]}>{VISIBILITY_LABELS[file.visibility]}</span>
            </Badge>
          </span>
        )}

        {canPick && (
          <Button
            variant="ghost"
            type="button"
            disabled={disabled || busy}
            onClick={() => !disabled && !busy && inputRef.current?.click()}
          >
            <Icon name="upload" size={14} />
            Subir
          </Button>
        )}
        {failed && upload.file !== null && (
          <Button variant="ghost" type="button" disabled={disabled} onClick={onRetry}>
            <Icon name="rotate-cw" size={14} />
            Reintentar
          </Button>
        )}
        {canDelete && (
          <Button
            variant="ghost"
            type="button"
            disabled={disabled}
            onClick={onDelete}
            aria-label={`Borrar el archivo de ${attachment.name}`}
          >
            <Icon name="trash-2" size={14} />
            Borrar
          </Button>
        )}
      </div>

      {busy && upload.phase === "uploading" && (
        <div
          role="progressbar"
          aria-label={`Progreso de la subida de ${attachment.name}`}
          aria-valuenow={percent}
          aria-valuemin={0}
          aria-valuemax={100}
          className="h-1.5 w-full overflow-hidden rounded-full bg-warm-100"
        >
          <div className="h-full bg-primary transition-all" style={{ width: `${percent}%` }} />
        </div>
      )}
      {failed && upload.message !== null && (
        <p className="text-sm font-medium text-danger">{upload.message}</p>
      )}
      {!failed && notice !== null && (
        <p role="note" className="mt-1 flex items-start gap-1.5 text-xs font-medium text-amber-700">
          <Icon name="triangle-alert" size={14} />
          <span>{notice}</span>
        </p>
      )}
      {file?.status_reason && (
        <p className="text-xs text-text-muted">
          {STATUS_REASON_LABELS[file.status_reason] ?? STATUS_REASON_FALLBACK}
        </p>
      )}

      {/* Sin `accept`: el backend valida la extensión contra el anexo oficial. */}
      {canUpload && (
        <input
          ref={inputRef}
          type="file"
          multiple
          disabled={disabled || busy}
          className="hidden"
          aria-label={`Elegir el archivo de ${attachment.name}`}
          data-testid={`attachment-input-${attachment.id}`}
          onChange={(event) => {
            const files = Array.from(event.target.files ?? []);
            event.target.value = "";
            if (files.length === 1) {
              onPick(files[0]);
            } else if (files.length > 1) {
              if (onPickMultiple) {
                onPickMultiple(files);
              } else {
                onPick(files[0]);
              }
            }
          }}
        />
      )}
    </li>
  );
}
