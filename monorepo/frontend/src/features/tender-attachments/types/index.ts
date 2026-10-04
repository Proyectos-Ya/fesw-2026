/** Estado de un anexo oficial para la empresa activa. Lo calcula el backend. */
export type AttachmentStatus = "missing" | "uploading" | "stored" | "rejected" | "unsupported";

export type AttachmentFileStatus = "uploading" | "stored" | "unsupported" | "rejected" | "purged";
export type AttachmentFileSource = "manual" | "extension" | "legacy_chat";
export type AttachmentVisibility = "private" | "shared";
export type AttachmentTrust = "pending" | "corroborated" | "conflict" | "rejected";

/** El archivo que la empresa activa ve para un anexo: el propio o uno compartido. */
export interface AttachmentFile {
  id: string;
  size_bytes: number;
  source: AttachmentFileSource;
  visibility: AttachmentVisibility;
  trust: AttachmentTrust;
  status: AttachmentFileStatus;
  /** Lo subió la empresa activa (y por eso puede borrarlo). */
  is_mine: boolean;
  created_at: string;
}

export interface OfficialAttachment {
  id: string;
  mp_document_id: number;
  name: string;
  /** Forma canónica calculada por el backend: contra esto se empareja un archivo soltado. */
  name_normalized: string;
  /** Minúsculas y sin punto; vacía si el nombre no trae una extensión reconocible. */
  ext: string;
  status: AttachmentStatus;
  file: AttachmentFile | null;
}

export interface UploadQuota {
  used: number;
  limit: number;
}

export interface TenderAttachments {
  official: OfficialAttachment[];
  /** ISO-8601 UTC con `Z`. `null` = la lista todavía no se sincroniza con Mercado Público. */
  list_synced_at: string | null;
  /** `null` sin empresa activa. */
  quota: UploadQuota | null;
  /** El rol puede subir (permiso `upload_attachments`) y hay almacenamiento configurado. */
  can_upload: boolean;
  max_upload_size_bytes: number;
}

export interface UploadUrlRequest {
  file_name: string;
  size_bytes: number;
  mime: string;
  /** Hex en minúsculas, 64 caracteres. */
  sha256: string;
}

/** Hay que subir el archivo: PUT directo a `url` con exactamente estas cabeceras. */
export interface UploadTicket {
  deduplicated: false;
  upload_id: string;
  url: string;
  method: "PUT";
  headers: Record<string, string>;
  expires_at: string;
}

/** Ya existe ese archivo para la empresa: no hay nada que subir. */
export interface UploadDeduplicated {
  deduplicated: true;
  file: AttachmentFile;
}

export type UploadUrlResponse = UploadTicket | UploadDeduplicated;

export const ATTACHMENT_STATUS_LABELS: Record<AttachmentStatus, string> = {
  missing: "Falta",
  uploading: "Subida incompleta",
  stored: "Subido",
  rejected: "Rechazado",
  unsupported: "Formato no legible",
};

export const VISIBILITY_LABELS: Record<AttachmentVisibility, string> = {
  private: "Solo tu empresa",
  shared: "Compartido",
};
