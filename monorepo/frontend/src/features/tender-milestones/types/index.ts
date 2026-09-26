export type MilestoneKind =
  | "publicacion"
  | "consultas"
  | "respuestas"
  | "visita_tecnica"
  | "cierre_postulacion"
  | "apertura"
  | "adjudicacion"
  | "entrega"
  | "firma_contrato"
  | "otro";

export type MilestoneSource = "mercado_publico" | "ia_documento";

export type MilestoneUrgency = "vencido" | "critico" | "proximo" | "normal";

export type CalendarProvider = "google";

export interface TenderMilestone {
  id: string;
  kind: MilestoneKind;
  title: string;
  description: string | null;
  source: MilestoneSource;
  source_excerpt: string | null;
  /** ISO-8601 UTC con sufijo `Z`. */
  due_at: string;
  has_time: boolean;
  urgency: MilestoneUrgency;
  synced_providers: CalendarProvider[];
}

export interface MilestoneList {
  milestones: TenderMilestone[];
  documents_count: number;
  discarded_count: number;
}

export const CALENDAR_PROVIDERS: readonly CalendarProvider[] = ["google"];

export const CALENDAR_PROVIDER_LABELS: Record<CalendarProvider, string> = {
  google: "Google Calendar",
};

export interface CalendarConnection {
  provider: CalendarProvider;
  connected: boolean;
  account_email: string | null;
  needs_reconnect: boolean;
}

export interface CalendarAuthorizationRequest {
  tender_id: string;
  milestone_ids: string[];
  /** Hora de Chile "HH:MM" para los hitos sin hora exacta. */
  default_time: string | null;
}

export interface CalendarAuthorizationResult {
  provider: CalendarProvider;
  tender_id: string;
  milestone_ids: string[];
  default_time: string | null;
  account_email: string | null;
}

export const MILESTONE_KIND_LABELS: Record<MilestoneKind, string> = {
  publicacion: "Publicación",
  consultas: "Consultas",
  respuestas: "Respuestas",
  visita_tecnica: "Visita técnica",
  cierre_postulacion: "Cierre de postulación",
  apertura: "Apertura de ofertas",
  adjudicacion: "Adjudicación",
  entrega: "Entrega",
  firma_contrato: "Firma de contrato",
  otro: "Otro hito",
};

export const MILESTONE_SOURCE_LABELS: Record<MilestoneSource, string> = {
  mercado_publico: "Mercado Público",
  ia_documento: "Extraído por IA",
};
