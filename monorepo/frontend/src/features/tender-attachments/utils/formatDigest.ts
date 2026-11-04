import { formatCLP } from "@/features/matches/utils/format";
import type { BudgetValue, VisitValue } from "../types";

export function formatDigestDate({
  fecha,
  hora,
}: {
  fecha: string;
  hora: string | null;
}): string {
  const partes = fecha.split("-");
  const fechaStr =
    partes.length === 3 ? `${partes[2]}-${partes[1]}-${partes[0]}` : fecha;
  return hora ? `${fechaStr}, ${hora}` : fechaStr;
}

export function formatBudget(budget: BudgetValue): string {
  if (budget.monto_clp != null) {
    const clp = formatCLP(budget.monto_clp);
    if (budget.incluye_iva === true) return `${clp} (IVA incluido)`;
    if (budget.incluye_iva === false) return `${clp} (neto)`;
    return clp;
  }
  return budget.monto_texto;
}

export function formatVisit(visit: VisitValue): string {
  if (
    visit.obligatoria == null &&
    !visit.fecha &&
    !visit.hora &&
    !visit.lugar
  ) {
    return "Sin detalle";
  }

  const partes: string[] = [];
  if (visit.obligatoria === true) {
    partes.push("Obligatoria");
  } else if (visit.obligatoria === false) {
    partes.push("Voluntaria");
  }

  if (visit.fecha) {
    partes.push(formatDigestDate({ fecha: visit.fecha, hora: visit.hora }));
  }

  if (visit.lugar) {
    partes.push(visit.lugar);
  }

  return partes.length > 0 ? partes.join(" · ") : "Sin detalle";
}
