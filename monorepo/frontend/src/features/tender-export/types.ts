export type ExportFormat = "pdf" | "xlsx";

/** Lo que se puede marcar o desmarcar antes de generar el Excel (HdU 19, criterio 5). */
export type ExportSection = "datos_generales" | "montos" | "items" | "hitos" | "analisis_ia";

export const EXPORT_SECTIONS: readonly ExportSection[] = [
  "datos_generales",
  "montos",
  "items",
  "hitos",
  "analisis_ia",
];

export const EXPORT_SECTION_LABELS: Record<ExportSection, { label: string; description: string }> = {
  datos_generales: {
    label: "Datos generales",
    description: "Código, organismo, ubicación y descripción.",
  },
  montos: { label: "Montos y cotización", description: "Monto disponible y tu cotización." },
  items: { label: "Datos técnicos", description: "Ítems solicitados con cantidades." },
  hitos: { label: "Fechas clave", description: "Publicación y cierre, en hora de Chile." },
  analisis_ia: {
    label: "Análisis de la IA",
    description: "Compatibilidad, recomendación y justificación.",
  },
};

export const EXPORT_FORMAT_LABELS: Record<ExportFormat, string> = { pdf: "PDF", xlsx: "Excel" };

export type ExportJobStatus = "processing" | "ready" | "failed";

export interface ExportJob {
  id: string;
  status: ExportJobStatus;
  format: ExportFormat;
  file_name: string;
  /** ISO-8601 UTC con sufijo `Z`. */
  created_at: string;
  finished_at: string | null;
  expires_at: string;
}

export interface DownloadedFile {
  blob: Blob;
  filename: string;
}

export type ExportResult =
  | ({ kind: "file" } & DownloadedFile)
  /** Tardó más de 10 s: sigue en segundo plano y avisa por correo (criterios 8 y 9). */
  | { kind: "queued"; jobId: string; message: string };
