import type { AttachmentFile, AttachmentVisibility } from "../types";

/** Avisos de la decisión 6. Solo sobre archivos propios: el estado de lo que suben
 * otras empresas nunca se deja ver. */
export const SHARING_NOTICES = {
  conflict: "Hay versiones distintas de este anexo; no se comparte hasta confirmarlo.",
  rejected:
    "Tu archivo no coincide con la versión confirmada de este anexo y queda solo para tu empresa. Si lo borras, verás la versión compartida.",
} as const;

export const VISIBILITY_HINTS: Record<AttachmentVisibility, string> = {
  private: "Solo lo ve tu empresa. Se comparte cuando otra fuente independiente confirma el mismo archivo.",
  shared: "Lo ven todas las empresas. No muestra quién lo subió.",
};

const WITH_CONTENT: ReadonlySet<AttachmentFile["status"]> = new Set(["stored", "unsupported"]);

export function sharingNotice(file: AttachmentFile | null): string | null {
  if (file === null || !file.is_mine || !WITH_CONTENT.has(file.status)) return null;
  if (file.trust === "conflict") return SHARING_NOTICES.conflict;
  if (file.trust === "rejected") return SHARING_NOTICES.rejected;
  return null;
}
