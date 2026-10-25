/**
 * Cotizaciones recibidas, en texto. `null` o ausente es que la fuente no lo
 * informó, no que no haya cotizaciones: por eso el chequeo es `== null` y no
 * `!count`, que trataría el 0 real como dato faltante.
 */
export function formatOffersCount(count: number | null | undefined): string {
  if (count == null) return "No disponible";
  return count === 1 ? "1 cotización" : `${count} cotizaciones`;
}
