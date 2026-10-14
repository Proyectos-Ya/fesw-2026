import type { Tender } from "../tenderTypes";
import { formatDateTime, parseApiDate } from "./format";

/** Etiqueta de una licitación en su segundo llamado. */
export const SECOND_CALL_LABEL = "Segundo llamado";

type CallFields = Pick<Tender, "call_number" | "first_call_closing_at" | "second_call_closing_at">;

/** Solo lo afirma un `2` explícito: `null` (licitación antigua) no es ni primero ni segundo. */
export function isSecondCall(tender: Pick<Tender, "call_number">): boolean {
  return tender.call_number === 2;
}

export interface CallClosingLine {
  key: "first" | "second";
  label: string;
  /** Fecha y hora de cierre en hora de Chile. */
  value: string;
  hint?: string;
}

const POSSIBLE_SECOND_CALL_HINT =
  "Mercado Público publica esta fecha desde el primer llamado; solo se usa si se abre un segundo llamado.";

/**
 * Cierres por llamado que muestra la ficha. En el primer llamado la fecha del
 * segundo es solo posible y no se presenta como un plazo. Sin fechas legibles
 * la lista queda vacía y la ficha se ve como antes.
 */
export function callClosingLines(tender: CallFields): CallClosingLine[] {
  const lines: CallClosingLine[] = [];
  if (parseApiDate(tender.first_call_closing_at) !== null) {
    lines.push({
      key: "first",
      label: "Cierre 1.er llamado",
      value: formatDateTime(tender.first_call_closing_at),
    });
  }
  if (parseApiDate(tender.second_call_closing_at) !== null) {
    const value = formatDateTime(tender.second_call_closing_at);
    lines.push(
      isSecondCall(tender)
        ? { key: "second", label: "Cierre 2.º llamado", value }
        : {
            key: "second",
            label: "Segundo llamado posible",
            value,
            hint: POSSIBLE_SECOND_CALL_HINT,
          },
    );
  }
  return lines;
}
