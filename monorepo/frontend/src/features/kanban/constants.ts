/**
 * Paleta de colores de columnas Kanban.
 * Alineada con `DEFAULT_COLUMN_COLORS` del backend
 * (`app/domain/entities/kanban.py`). No duplicar literales en otros archivos.
 */
export const PALETTE: readonly string[] = [
  "#A99A7C",
  "#BF6E4A",
  "#5C7A52",
  "#35645B",
  "#E08E2B",
  "#A65A2E",
  "#244024",
] as const;

export const HEX_RE = /^#[0-9A-Fa-f]{6}$/;
