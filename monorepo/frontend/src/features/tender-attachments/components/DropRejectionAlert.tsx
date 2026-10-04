"use client";

import { Button } from "@/features/shared/components/Button";
import type { OfficialAttachment } from "../types";
import type { RejectedFile } from "../utils/matchFiles";

interface DropRejectionAlertProps {
  rejections: readonly RejectedFile[];
  official: readonly OfficialAttachment[];
  onClose: () => void;
}

/** Qué archivos del último arrastre no se pudieron asignar a un anexo, y por qué. */
export function DropRejectionAlert({ rejections, official, onClose }: DropRejectionAlertProps) {
  const unknown = rejections.filter((r) => r.reason === "no_match");
  const ambiguous = rejections.filter((r) => r.reason === "ambiguous");
  const duplicated = rejections.filter((r) => r.reason === "duplicate");

  return (
    <div
      role="alert"
      className="mt-3 flex flex-col gap-2 rounded-md border border-warning/30 bg-warning-soft/40 px-4 py-3 text-sm text-text-strong"
    >
      {unknown.length > 0 && (
        <div>
          <p>
            No reconocimos estos archivos: {unknown.map((r) => r.fileName).join(", ")}. Cada
            archivo tiene que llamarse como un anexo oficial:
          </p>
          <ul aria-label="Nombres esperados" className="mt-1 list-disc pl-5 text-text-muted">
            {official.map((attachment) => (
              <li key={attachment.id}>{attachment.name}</li>
            ))}
          </ul>
        </div>
      )}
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
