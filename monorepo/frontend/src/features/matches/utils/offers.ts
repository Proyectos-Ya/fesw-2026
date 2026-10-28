import type { Tender } from "../tenderTypes";

/**
 * Cotizaciones recibidas, en texto. `null` o ausente es que la fuente no lo
 * informó, no que no haya cotizaciones: por eso el chequeo es `== null` y no
 * `!count`, que trataría el 0 real como dato faltante.
 */
export function formatOffersCount(count: number | null | undefined): string {
  if (count == null) return "No disponible";
  return count === 1 ? "1 cotización" : `${count} cotizaciones`;
}

export interface OffersSummary {
  /** Lo que va en grande en la tarjeta. */
  value: string;
  /** Desglose por llamado, solo en segundo llamado. */
  detail?: string;
}

type OffersFields = Pick<Tender, "call_number" | "received_offers_count" | "first_call_offers_count">;

/**
 * Total de cotizaciones de los dos llamados. La API cuenta solo el llamado
 * actual, así que en segundo llamado se suma la última cifra vista del
 * primero. Si esa cifra falta, se muestra la del segundo sin inventar el total.
 */
export function offersSummary(tender: OffersFields): OffersSummary {
  const actual = tender.received_offers_count;
  if (tender.call_number !== 2 || actual == null) {
    return { value: formatOffersCount(actual) };
  }
  const primero = tender.first_call_offers_count;
  if (primero == null) {
    return { value: `${actual} en el 2.º llamado`, detail: "1.er llamado: No disponible" };
  }
  return {
    value: formatOffersCount(primero + actual),
    detail: `${primero} en el 1.er llamado y ${actual} en el 2.º`,
  };
}
