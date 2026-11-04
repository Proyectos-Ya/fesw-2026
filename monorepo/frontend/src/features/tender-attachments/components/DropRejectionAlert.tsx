"use client";

import { Button } from "@/features/shared/components/Button";
import type { OfficialAttachment } from "../types";
import type { RejectedFile } from "../utils/matchFiles";

interface DropRejectionAlertProps {
  rejections: readonly RejectedFile[];
  official?: readonly OfficialAttachment[];
  onClose: () => void;
}

/** Qué archivos del último arrastre tuvieron conflicto (ambigüedad o duplicado). */
export function DropRejectionAlert({ rejections, onClose }: DropRejectionAlertProps) {
  const ambiguous = rejections.filter((r) => r.reason === "ambiguous");
  const duplicated = rejections.filter((r) => r.reason === "duplicate");

  if (ambiguous.length === 0 && duplicated.length === 0) {
    return null;
  }

  return (
    <div
      role="alert"
      className="mt-3 flex flex-col gap-2 rounded-md border border-warning/30 bg-warning-soft/40 px-4 py-3 text-sm text-text-strong"
    >
      {ambiguous.map((r) => (
        <p key={`ambiguous-${r.fileName}`}>
          «{r.fileName}» coincide con más de un anexo: súbelo con el botón «Subir» de su fila.
        </p>
      ))}
      {duplicated.map((r) => (
        <p key={`duplicate-${r.fileName}`}>
          «{r.fileName}» se repite: subimos solo el primero.
        </p>
      ))}
      <Button variant="ghost" type="button" onClick={onClose} className="self-end">
        Cerrar
      </Button>
    </div>
  );
}
