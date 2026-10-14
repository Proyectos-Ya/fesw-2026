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

function createDynamicAttachment(file: File): OfficialAttachment {
  const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
  return {
    id:
      typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
        ? crypto.randomUUID()
        : `dyn-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
    mp_document_id: 0,
    name: file.name,
    name_normalized: normalizeAttachmentName(file.name),
    ext,
    status: "missing",
    file: null,
    processing: null,
  };
}

/**
 * Asigna cada archivo soltado a una fila oficial o disponible.
 *
 * - Coincidencia por nombre normalizado (ignora tildes, mayúsculas y sufijos "(1)").
 * - Si el nombre no coincide, asigna a los anexos disponibles sin restringir la extensión.
 * - Si no hay filas disponibles o la licitación no tiene anexos oficiales, genera
 *   un slot dinámico para el archivo.
 * - Más de una fila con el mismo nombre normalizado: `ambiguous`.
 * - Filas repetidas para el mismo anexo oficial: `duplicate`.
 */
export function matchDroppedFiles(
  files: readonly File[],
  official: readonly OfficialAttachment[],
): DropMatch {
  if (official.length === 0) {
    return {
      matched: files.map((file) => ({
        file,
        attachment: createDynamicAttachment(file),
      })),
      rejected: [],
    };
  }

  const byName = new Map<string, OfficialAttachment[]>();
  for (const attachment of official) {
    const rows = byName.get(attachment.name_normalized) ?? [];
    rows.push(attachment);
    byName.set(attachment.name_normalized, rows);
  }

  const matched: MatchedFile[] = [];
  const rejected: RejectedFile[] = [];
  const taken = new Set<string>();
  const unmatchedFiles: File[] = [];

  // Paso 1: Intentar coincidencia directa por nombre normalizado
  for (const file of files) {
    const rows = byName.get(normalizeAttachmentName(file.name)) ?? [];
    if (rows.length === 1) {
      if (taken.has(rows[0].id)) {
        rejected.push({ fileName: file.name, reason: "duplicate" });
      } else {
        taken.add(rows[0].id);
        matched.push({ file, attachment: rows[0] });
      }
    } else if (rows.length > 1) {
      rejected.push({ fileName: file.name, reason: "ambiguous" });
    } else {
      unmatchedFiles.push(file);
    }
  }

  // Paso 2: Para archivos sin coincidencia de nombre, asignar a filas disponibles
  const available = official.filter((a) => !taken.has(a.id));
  // Priorizar las filas que no tienen archivo subido aún (missing / file === null)
  available.sort((a, b) => {
    const aMissing = a.file === null || a.status === "missing" ? 0 : 1;
    const bMissing = b.file === null || b.status === "missing" ? 0 : 1;
    return aMissing - bMissing;
  });

  for (const file of unmatchedFiles) {
    if (available.length > 0) {
      const attachment = available.shift()!;
      taken.add(attachment.id);
      matched.push({ file, attachment });
    } else {
      matched.push({ file, attachment: createDynamicAttachment(file) });
    }
  }

  // Conservar el orden original en que se soltaron los archivos
  const fileOrder = new Map(files.map((f, i) => [f, i]));
  matched.sort((a, b) => (fileOrder.get(a.file) ?? 0) - (fileOrder.get(b.file) ?? 0));

  return { matched, rejected };
}
