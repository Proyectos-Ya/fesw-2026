/**
 * Ficha pública de un proceso de Compra Ágil en el buscador oficial de
 * Mercado Público. Los códigos COT no existen en la ficha de licitaciones
 * tradicionales (RFB/DetailsAcquisition.aspx), por lo que el enlace debe
 * apuntar al buscador de Compra Ágil.
 */
export function compraAgilFichaUrl(code: string): string {
  return `https://buscador.mercadopublico.cl/ficha?code=${encodeURIComponent(code)}`;
}
