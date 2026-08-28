export type ClosingTone = "danger" | "warning" | "neutral" | "expired";

export interface ClosingInfo {
  days: number;
  label: string;
  tone: ClosingTone;
}

const clpFormatter = new Intl.NumberFormat("es-CL", {
  style: "currency",
  currency: "CLP",
  maximumFractionDigits: 0,
});

export function formatCLP(amount: number | null | undefined): string {
  if (amount == null || Number.isNaN(amount)) return "Monto no informado";
  return clpFormatter.format(amount);
}

/**
 * Normalize a match score to the 0..100 range.
 * Backend may emit either 0..1 (cosine/reranker) or 0..100 depending on the
 * weighting service. Auto-detect by checking the value's magnitude.
 */
export function normalizeScore(raw: number): number {
  if (!Number.isFinite(raw)) return 0;
  const scaled = raw <= 1 ? raw * 100 : raw;
  return Math.max(0, Math.min(100, scaled));
}

/** ISO-8601 con zona explícita: sufijo `Z` u offset `±HH:MM` / `±HHMM`. */
const HAS_TIMEZONE = /(?:Z|[+-]\d{2}:?\d{2})$/i;
/** ISO-8601 con componente horario (lo distingue de un `YYYY-MM-DD` suelto). */
const HAS_TIME = /\d{2}:\d{2}/;

/**
 * Convierte una fecha de la API en un `Date`.
 *
 * El backend persiste todo en UTC y serializa con sufijo `Z`. Si un endpoint
 * devuelve el ISO sin offset, `new Date()` lo interpretaría como hora **local**
 * y mostraría la hora corrida; por eso aquí se marca explícitamente como UTC,
 * respetando la convención de persistencia del backend.
 *
 * Un `YYYY-MM-DD` sin hora ya se interpreta como UTC según el estándar, así que
 * se deja intacto.
 */
export function parseApiDate(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const normalized = HAS_TIME.test(iso) && !HAS_TIMEZONE.test(iso) ? `${iso}Z` : iso;
  const parsed = new Date(normalized);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

const MS_PER_DAY = 1000 * 60 * 60 * 24;

export function daysUntilClosing(closingAtIso: string, now: Date = new Date()): ClosingInfo {
  const closing = parseApiDate(closingAtIso);
  if (closing === null) {
    return { days: 0, label: "Fecha no disponible", tone: "neutral" };
  }
  const diffMs = closing.getTime() - now.getTime();
  const days = Math.ceil(diffMs / MS_PER_DAY);

  if (days < 0) return { days, label: "Cerrada", tone: "expired" };
  if (days === 0) return { days, label: "Cierra hoy", tone: "danger" };
  if (days === 1) return { days, label: "Cierra mañana", tone: "danger" };
  if (days <= 3) return { days, label: `Cierra en ${days} días`, tone: "danger" };
  if (days <= 7) return { days, label: `Cierra en ${days} días`, tone: "warning" };
  return { days, label: `Cierra en ${days} días`, tone: "neutral" };
}

const closingFormatter = new Intl.DateTimeFormat("es-CL", {
  timeZone: "America/Santiago",
  day: "2-digit",
  month: "short",
  year: "numeric",
});

export function formatClosingDate(closingAtIso: string): string {
  const closing = parseApiDate(closingAtIso);
  if (closing === null) return "—";
  return closingFormatter.format(closing).replace(/\u00a0/g, " ");
}

const dateTimeFormatter = new Intl.DateTimeFormat("es-CL", {
  timeZone: "America/Santiago",
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});


export function formatDateTime(iso: string | null | undefined): string {
  const d = parseApiDate(iso);
  if (d === null) return "—";
  return dateTimeFormatter.format(d).replace(/\u00a0/g, " ");
}
