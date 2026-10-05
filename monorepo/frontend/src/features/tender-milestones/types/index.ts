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

/** `critico`: le quedan 5 días de calendario o menos y se destaca en rojo (criterio 9). */
export type MilestoneUrgency = "vencido" | "critico" | "normal";

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
  /** Días de anticipación del recordatorio; `null` = sin recordatorio. */
  reminder_days_before: ReminderDaysBefore | null;
}

/** Las anticipaciones que ofrece la interfaz; el backend valida las mismas. */
export const REMINDER_DAYS_OPTIONS = [1, 3, 7] as const;

export type ReminderDaysBefore = (typeof REMINDER_DAYS_OPTIONS)[number];

export const REMINDER_LABELS: Record<ReminderDaysBefore, string> = {
  1: "1 día antes",
  3: "3 días antes",
  7: "1 semana antes",
};

export interface MilestoneReminderResponse {
  milestone_id: string;
  reminder_days_before: ReminderDaysBefore | null;
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

export interface MilestoneSyncResponse {
  results: { milestone_id: string; synced: boolean }[];
  failed_count: number;
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
