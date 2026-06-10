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

const MS_PER_DAY = 1000 * 60 * 60 * 24;

export function daysUntilClosing(closingAtIso: string, now: Date = new Date()): ClosingInfo {
  const closing = new Date(closingAtIso);
  if (Number.isNaN(closing.getTime())) {
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
  day: "2-digit",
  month: "short",
  year: "numeric",
});

export function formatClosingDate(closingAtIso: string): string {
  const closing = new Date(closingAtIso);
  if (Number.isNaN(closing.getTime())) return "—";
  return closingFormatter.format(closing);
}
