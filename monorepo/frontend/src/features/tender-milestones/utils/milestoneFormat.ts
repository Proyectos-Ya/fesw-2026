import type { BadgeTone } from "@/features/shared/components/Badge";
import { parseApiDate } from "@/features/matches/utils/format";

import type { MilestoneUrgency } from "../types";

const MS_PER_DAY = 1000 * 60 * 60 * 24;

// Reloj de 24 horas: así aparecen los plazos en las bases ("a las 15:00").
const withTime = new Intl.DateTimeFormat("es-CL", {
  timeZone: "America/Santiago",
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

const dateOnly = new Intl.DateTimeFormat("es-CL", {
  timeZone: "America/Santiago",
  day: "2-digit",
  month: "short",
  year: "numeric",
});

const isoDay = new Intl.DateTimeFormat("en-CA", {
  timeZone: "America/Santiago",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

/** Número de día calendario en Chile: "hoy" y "mañana" se cuentan por fecha, no por horas. */
function chileDay(date: Date): number {
  const [year, month, day] = isoDay.format(date).split("-").map(Number);
  return Date.UTC(year, month - 1, day) / MS_PER_DAY;
}

export function formatMilestoneDate(iso: string, hasTime: boolean): string {
  const date = parseApiDate(iso);
  if (date === null) return "—";
  const formatter = hasTime ? withTime : dateOnly;
  return formatter.format(date).replace(/[  ]/g, " ");
}

const URGENCY_TONES: Record<MilestoneUrgency, BadgeTone> = {
  vencido: "neutral",
  critico: "danger",
  proximo: "warning",
  normal: "neutral",
};

/** La urgencia la decide el backend; acá solo se traduce a etiqueta y color. */
export function urgencyBadge(
  urgency: MilestoneUrgency,
  dueAtIso: string,
  now: Date = new Date(),
): { label: string; tone: BadgeTone } {
  const tone = URGENCY_TONES[urgency];
  if (urgency === "vencido") return { label: "Vencido", tone };
  const dueAt = parseApiDate(dueAtIso);
  if (dueAt === null) return { label: "—", tone };
  const days = Math.max(0, chileDay(dueAt) - chileDay(now));
  if (days === 0) return { label: "Hoy", tone };
  if (days === 1) return { label: "Mañana", tone };
  return { label: `En ${days} días`, tone };
}
