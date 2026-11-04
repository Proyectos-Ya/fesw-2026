/**
 * Ficha pública de un proceso de Compra Ágil en el buscador oficial de
 * Mercado Público. Los códigos COT no existen en la ficha de licitaciones
 * tradicionales (RFB/DetailsAcquisition.aspx), por lo que el enlace debe
 * apuntar al buscador de Compra Ágil.
 */
export function compraAgilFichaUrl(code: string): string {
  return `https://buscador.mercadopublico.cl/ficha?code=${encodeURIComponent(code)}`;
}

/** Ficha de Compra Ágil desde donde el proveedor cotiza (requiere sesión en Mercado Público). */
export function compraAgilCotizacionUrl(code: string): string {
  return `https://compra-agil.mercadopublico.cl/resumen-cotizacion/${encodeURIComponent(code)}`;
}

export function isCompraAgilCode(code: string): boolean {
  return /-COT\d+$/i.test(code.trim());
}
