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
  /** Visibilidad efectiva que calcula el backend: `shared` también para el archivo propio ya confirmado. La etiqueta se lee de acá; no se recalcula con `trust`. */
  visibility: AttachmentVisibility;
  trust: AttachmentTrust;
  status: AttachmentFileStatus;
  status_reason?: string | null;
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
  processing?: AttachmentProcessingStatus | null;
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
  processing_enabled?: boolean;
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

export type AttachmentProcessingStatus = "processing" | "ready" | "failed" | "unsupported";

export const PROCESSING_LABELS: Record<Exclude<AttachmentProcessingStatus, "unsupported">, string> = {
  processing: "Leyendo…",
  ready: "Resumen listo",
  failed: "No se pudo leer",
};

export const STATUS_REASON_LABELS: Record<string, string> = {
  checksum_mismatch: "El archivo guardado no coincide con el que subiste. Vuelve a subirlo.",
  content_mismatch: "El contenido no corresponde al tipo de archivo.",
  macro_enabled: "El archivo trae macros y no lo procesamos por seguridad.",
  archive_too_large: "El archivo comprimido es demasiado grande para leerlo de forma segura.",
  legacy_format: "Formato antiguo de Office (.doc o .xls): no lo podemos leer.",
  encrypted_or_legacy: "El archivo está protegido con contraseña o en un formato antiguo.",
  format_not_supported: "Este tipo de archivo no se puede resumir.",
  no_text: "El documento no tiene texto legible.",
};

export const STATUS_REASON_FALLBACK = "No pudimos procesar este archivo.";

export const AI_NOTICE =
  "Resumen generado con IA a partir de los anexos. Puede tener errores: revisa las citas y los documentos oficiales antes de postular.";

// --- Tipos de Digest (Plan 233, Decisión 4 y 5) ---

export interface DigestCitation {
  documento: string;
  pagina_u_hoja: string | null;
  cita: string;
  verificada: boolean;
  anexo_id?: string;
  archivo_id?: string;
}

export interface DateValue {
  fecha: string;
  hora: string | null;
}

export interface BudgetValue {
  monto_clp: number | null;
  incluye_iva: boolean | null;
  monto_texto: string;
}

export interface VisitValue {
  obligatoria: boolean | null;
  fecha: string | null;
  hora: string | null;
  lugar: string | null;
}

export interface DigestAlternative<T> {
  valor: T;
  citas: DigestCitation[];
}

export interface DigestField<T> {
  valor: T | null;
  en_conflicto: boolean;
  alternativas: DigestAlternative<T>[];
  citas: DigestCitation[];
}

export interface DigestFields {
  presupuesto: DigestField<BudgetValue> | null;
  fecha_publicacion: DigestField<DateValue> | null;
  fecha_cierre_primer_llamado: DigestField<DateValue> | null;
  fecha_cierre_segundo_llamado: DigestField<DateValue> | null;
  visita_tecnica: DigestField<VisitValue> | null;
}

export interface DigestRequirement {
  descripcion: string;
  tipo: string;
  obligatorio: boolean | null;
  citas: DigestCitation[];
}

export interface DigestItem {
  descripcion: string;
  cantidad: number | null;
  unidad: string | null;
  citas: DigestCitation[];
}

export interface DigestDeliverable {
  descripcion: string;
  plazo: string | null;
  citas: DigestCitation[];
}

export interface DigestNote {
  descripcion: string;
  citas: DigestCitation[];
}

export interface DigestSummary {
  anexo_id: string;
  documento: string;
  texto: string;
  citas: DigestCitation[];
}

export interface DigestOtherQuote {
  tema: string;
  citas: DigestCitation[];
}

export interface DigestDiscrepancy {
  tipo: "anexo_vs_anexo" | "anexo_vs_api";
  campo: "presupuesto" | "fecha_publicacion" | "fecha_cierre_primer_llamado" | "fecha_cierre_segundo_llamado" | "visita_tecnica";
  tema: string;
  descripcion: string;
  campo_api: string | null;
  valor_api: string | null;
  valores_anexos: string[];
  fuentes: DigestCitation[];
}

export interface DigestSource {
  anexo_id: string;
  archivo_id: string;
  documento: string;
  visibilidad: AttachmentVisibility;
  citas_total: number;
  citas_verificadas: number;
  texto_disponible: boolean;
  modelo: string;
  prompt_version: string;
  procesado_en: string;
}

export interface TenderDigestData {
  campos: DigestFields;
  requisitos: DigestRequirement[];
  items: DigestItem[];
  entregables: DigestDeliverable[];
  puntos_a_tener_en_cuenta: DigestNote[];
  resumenes: DigestSummary[];
  otras_citas: DigestOtherQuote[];
  discrepancias: DigestDiscrepancy[];
  fuentes: DigestSource[];
}

export interface TenderDigest {
  id: string;
  tender_id: string;
  scope: "shared" | "workspace";
  version: number;
  status: "ready" | "empty";
  pending_sources: number;
  data: TenderDigestData;
  created_at: string;
}
