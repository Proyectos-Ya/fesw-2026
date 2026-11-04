/**
 * Textos y rutas del formulario de Compra Ágil observados el 2026-11-04 en
 * compra-agil.mercadopublico.cl. Los controles no tienen name ni id estables, así que
 * se ubican por el texto visible. Si Mercado Público cambia la interfaz, se ajusta aquí.
 */
export const COMPRA_AGIL = {
  host: "compra-agil.mercadopublico.cl",
  pathPattern: /^\/resumen-cotizacion\/([^/]+)\/?$/,
  headerPattern: /Detalle de la cotización\s+(\S+)/,
  participarHeading: "Participar de la Compra Ágil",
  productIdPattern: /^ID:\s*(\d+)$/,
  labels: {
    unitPrice: "Valor unitario",
    shipping: "Despacho",
    detail: "Detalle cotización",
    validity: "Fecha de vigencia",
    annex: "documento anexo (opcional)",
  },
  detailMaxLength: 255,
  annexMaxBytes: 20 * 1024 * 1024,
  annexExtensions: [".doc", ".docx", ".xls", ".xlsx", ".pdf"],
} as const;
