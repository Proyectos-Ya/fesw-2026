/**
 * Dirección y plazo de entrega del detalle de Compra Ágil (#294). Sin dato,
 * los textos son los que pide HU-22 (#314) para la ficha.
 */
export function formatDeliveryAddress(address: string | null | undefined): string {
  const limpia = address?.trim();
  return limpia ? limpia : "Dirección de entrega no disponible";
}

/** `== null` y no `!days`: un plazo de 0 días es un dato real. */
export function formatDeliveryTerm(days: number | null | undefined): string {
  if (days == null) return "Plazo de entrega no disponible";
  return days === 1 ? "1 día" : `${days} días`;
}
