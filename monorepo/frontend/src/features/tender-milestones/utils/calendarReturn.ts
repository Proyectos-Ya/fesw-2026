import type { CalendarAuthorizationResult } from "../types";

/**
 * Licitación desde la que se salió a autorizar el calendario.
 *
 * Si el usuario cancela en Google, la respuesta no trae nada propio de la app
 * más que el `state`, que es opaco; esto permite ofrecerle volver a donde estaba.
 */
const KEY = "proyectosya.calendar-return-tender";

export function rememberCalendarReturnTender(tenderId: string): void {
  try {
    window.sessionStorage.setItem(KEY, tenderId);
  } catch {
    // Sin almacenamiento (modo privado, bloqueado): el retorno cae a /matches.
  }
}

export function consumeCalendarReturnTender(): string | null {
  try {
    const tenderId = window.sessionStorage.getItem(KEY);
    window.sessionStorage.removeItem(KEY);
    return tenderId;
  } catch {
    return null;
  }
}

const PENDING_KEY = "proyectosya.calendar-pending-sync";

/** Lo que el usuario pidió sincronizar antes de ir a autorizar; se completa al volver. */
export function savePendingCalendarSync(pending: CalendarAuthorizationResult): void {
  try {
    window.sessionStorage.setItem(PENDING_KEY, JSON.stringify(pending));
  } catch {
    // Sin almacenamiento el usuario tendrá que volver a pulsar "Sincronizar".
  }
}

export function consumePendingCalendarSync(tenderId: string): CalendarAuthorizationResult | null {
  try {
    const raw = window.sessionStorage.getItem(PENDING_KEY);
    if (raw === null) return null;
    const pending: unknown = JSON.parse(raw);
    if (!isPendingSync(pending) || pending.tender_id !== tenderId) return null;
    window.sessionStorage.removeItem(PENDING_KEY);
    return pending;
  } catch {
    return null;
  }
}

function isPendingSync(value: unknown): value is CalendarAuthorizationResult {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.tender_id === "string" &&
    typeof v.provider === "string" &&
    Array.isArray(v.milestone_ids) &&
    v.milestone_ids.every((id) => typeof id === "string") &&
    (v.default_time === null || typeof v.default_time === "string")
  );
}
