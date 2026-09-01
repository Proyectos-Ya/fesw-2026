import type { Tender } from "@/features/matches/tenderTypes";

export type DeliveryMode = "immediate" | "daily_digest";
export type DeliveryStatus = "pending" | "sent" | "failed_permanent";
export type DeliveryKind = "immediate" | "digest";

export interface NotificationItem {
  id: string;
  tender_id: string;
  /** Compatibilidad ya convertida a porcentaje por el backend. */
  score_pct: number;
  read_at: string | null;
  created_at: string;
  /** También es `true` si la licitación desapareció de la base. */
  is_closed: boolean;
  tender: Tender | null;
}

export interface NotificationPreferences {
  enabled: boolean;
  /** Umbral en porcentaje (1–100). El backend guarda la escala 0..1. */
  threshold_pct: number;
  delivery_mode: DeliveryMode;
  /** El sistema lo apaga solo si el proveedor de correo rechaza la dirección. */
  email_delivery_enabled: boolean;
  last_failure_reason: string | null;
  last_failure_at: string | null;
}

export interface UpdatePreferencesPayload {
  enabled?: boolean;
  threshold_pct?: number;
  delivery_mode?: DeliveryMode;
  reactivate_email?: boolean;
}

export interface NotificationDelivery {
  id: string;
  kind: DeliveryKind;
  status: DeliveryStatus;
  attempts: number;
  last_error: string | null;
  next_attempt_at: string;
  sent_at: string | null;
  created_at: string;
  notification_ids: string[];
}

export interface UnreadCount {
  count: number;
}

export interface TenderDetail {
  tender: Tender;
  score_pct: number | null;
  is_closed: boolean;
}
