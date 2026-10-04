import type { OfficialAttachment } from "../types";
import { normalizeAttachmentName } from "./attachmentNames";

export type DropRejectionReason = "no_match" | "ambiguous" | "duplicate";

export interface MatchedFile {
  file: File;
  attachment: OfficialAttachment;
}

export interface RejectedFile {
  fileName: string;
  reason: DropRejectionReason;
}

export interface DropMatch {
  matched: MatchedFile[];
  rejected: RejectedFile[];
}

/**
 * Asigna cada archivo soltado a la fila oficial que le corresponde por nombre.
 *
 * - Sin fila con ese nombre normalizado: `no_match`.
 * - Más de una fila con el mismo nombre normalizado ("Anexo.pdf" y "Anexo (2).pdf"):
 *   `ambiguous`; el botón "Subir" de cada fila resuelve el caso.
 * - Una fila que ya tomó otro archivo de este mismo drop: `duplicate`.
 *
 * El orden de `matched` es el de los archivos soltados.
 */
export function matchDroppedFiles(
  files: readonly File[],
  official: readonly OfficialAttachment[],
): DropMatch {
  const byName = new Map<string, OfficialAttachment[]>();
  for (const attachment of official) {
    const rows = byName.get(attachment.name_normalized) ?? [];
    rows.push(attachment);
    byName.set(attachment.name_normalized, rows);
  }

  const matched: MatchedFile[] = [];
  const rejected: RejectedFile[] = [];
  const taken = new Set<string>();
  for (const file of files) {
    const rows = byName.get(normalizeAttachmentName(file.name)) ?? [];
    if (rows.length === 0) {
      rejected.push({ fileName: file.name, reason: "no_match" });
    } else if (rows.length > 1) {
      rejected.push({ fileName: file.name, reason: "ambiguous" });
    } else if (taken.has(rows[0].id)) {
      rejected.push({ fileName: file.name, reason: "duplicate" });
    } else {
      taken.add(rows[0].id);
      matched.push({ file, attachment: rows[0] });
    }
  }
  return { matched, rejected };
}
