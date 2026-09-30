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

/** Zona en la que se cuentan los días y se muestra la hora de cierre. */
const CLOSING_TIME_ZONE = "America/Santiago";

/** Fecha de calendario en Chile, como `YYYY-MM-DD` (formato de `en-CA`). */
const chileDayFormatter = new Intl.DateTimeFormat("en-CA", {
  timeZone: CLOSING_TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

const closingTimeFormatter = new Intl.DateTimeFormat("es-CL", {
  timeZone: CLOSING_TIME_ZONE,
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

/** Días de calendario en Chile entre `desde` y `hasta` (negativo si ya pasó). */
function calendarDaysBetween(desde: Date, hasta: Date): number {
  const dia = (d: Date) => Date.parse(`${chileDayFormatter.format(d)}T00:00:00Z`);
  return Math.round((dia(hasta) - dia(desde)) / MS_PER_DAY);
}

/**
 * Estados que ya no admiten postulación, con el nombre que se muestra. Un
 * estado ausente o `publicada` deja que decida la fecha.
 */
const INACTIVE_STATUS_LABELS: Readonly<Record<string, string>> = {
  cerrada: "Cerrada",
  desierta: "Desierta",
  cancelada: "Cancelada",
  proveedor_seleccionado: "Cerrada",
  oc_emitida: "Cerrada",
  desconocido: "Cerrada",
};

/**
 * Viñeta de cierre de una licitación.
 *
 * "Cerrada" la decide el **estado** que guarda el backend y no la fecha sola:
 * el estado lo actualiza un proceso periódico, y entre una pasada y otra una
 * licitación puede tener el plazo vencido y seguir figurando publicada. Ese
 * caso se dice tal cual ("Cerró hoy 10:00") mientras sea del mismo día; si
 * venció un día anterior, la fecha basta para darla por cerrada.
 *
 * Los días se cuentan en calendario de Chile: una que cierra a las 18:00 de
 * hoy "cierra hoy" aunque falten menos de 24 horas.
 */
export function daysUntilClosing(
  closingAtIso: string,
  statusCode?: string | null,
  now: Date = new Date(),
): ClosingInfo {
  const closing = parseApiDate(closingAtIso);
  if (closing === null) {
    return { days: 0, label: "Fecha no disponible", tone: "neutral" };
  }
  const days = calendarDaysBetween(now, closing);

  const inactiveLabel = statusCode ? INACTIVE_STATUS_LABELS[statusCode] : undefined;
  if (inactiveLabel) return { days, label: inactiveLabel, tone: "expired" };

  const hora = closingTimeFormatter.format(closing);
  if (closing.getTime() <= now.getTime()) {
    return days === 0
      ? { days, label: `Cerró hoy ${hora}`, tone: "expired" }
      : { days, label: "Cerrada", tone: "expired" };
  }
  if (days === 0) return { days, label: `Cierra hoy ${hora}`, tone: "danger" };
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
