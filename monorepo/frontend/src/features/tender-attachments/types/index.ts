/** Estado de un anexo oficial. Hoy solo "missing": la subida llega en la decisión 2. */
export type AttachmentStatus = "missing";

export interface OfficialAttachment {
  id: string;
  mp_document_id: number;
  name: string;
  /** Minúsculas y sin punto; vacía si el nombre no trae una extensión reconocible. */
  ext: string;
  status: AttachmentStatus;
}

export interface TenderAttachments {
  official: OfficialAttachment[];
  /** ISO-8601 UTC con `Z`. `null` = la lista todavía no se sincroniza con Mercado Público. */
  list_synced_at: string | null;
}

export const ATTACHMENT_STATUS_LABELS: Record<AttachmentStatus, string> = { missing: "Falta" };
