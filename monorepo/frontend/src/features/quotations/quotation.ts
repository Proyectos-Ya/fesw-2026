export interface Material {
  description: string;
  unit: string;
  quantity: string;
  unit_price: string;
}

export type Currency = "CLP" | "USD" | "EUR" | "UF";
export interface TenderMaterial { name: string; description: string | null; unit_of_measure?: string | null; quantity?: number | null; }

export function materialsFromTender(items: TenderMaterial[]): Material[] {
  return items.flatMap(item => {
    const description = item.description?.trim() || item.name.trim();
    const quantity = item.quantity;
    const validQuantity = typeof quantity === "number" && Number.isInteger(quantity) && quantity > 0 && quantity <= 999999999;
    return description ? [{ description, unit: item.unit_of_measure?.trim() || "", quantity: validQuantity ? String(quantity) : "", unit_price: "" }] : [];
  });
}
export interface Quotation {
  id: string;
  supplier_id: string;
  tender_id: string;
  currency: Currency;
  items: Material[];
  total: string;
  updated_at: string;
}

function validInteger(value: string, digits: number): boolean {
  return new RegExp(`^\\d{1,${digits}}$`).test(value);
}

// El almacenamiento histórico puede devolver "2.000"; solo se quitan ceros.
export function normalizeInteger(value: string): string {
  return value.replace(/\.0+$/, "");
}

/** Formato chileno exacto: no convierte importes grandes a Number. */
export function formatInteger(value: string): string {
  return /^\d+$/.test(value) ? value.replace(/\B(?=(\d{3})+(?!\d))/g, ".") : value;
}

export function validate(items: Material[]): string[] {
  if (!items.length) return ["Agrega al menos un material."];
  if (items.length > 200) return ["Puedes agregar hasta 200 materiales."];
  return items.flatMap((item, index) => {
    const errors: string[] = [];
    const label = `Material ${index + 1}: `;
    if (!item.description.trim() || item.description.trim().length > 500) errors.push(label + "indica una descripción de hasta 500 caracteres.");
    if (!item.unit.trim() || item.unit.trim().length > 40) errors.push(label + "indica una unidad de hasta 40 caracteres.");
    if (!validInteger(item.quantity, 9) || BigInt(item.quantity) <= BigInt(0)) errors.push(label + "la cantidad debe ser un entero mayor que cero, de hasta 9 dígitos.");
    if (!validInteger(item.unit_price, 12)) errors.push(label + "el precio debe ser un entero cero o positivo, de hasta 12 dígitos.");
    return errors;
  });
}

export function subtotal(item: Material): string {
  if (!validInteger(item.quantity, 9) || BigInt(item.quantity) <= BigInt(0) || !validInteger(item.unit_price, 12)) return "";
  return (BigInt(item.quantity) * BigInt(item.unit_price)).toString();
}

export function total(items: Material[]): string {
  const subtotals = items.map(subtotal);
  if (!items.length || subtotals.some(value => value === "")) return "";
  return subtotals.reduce((sum, value) => sum + BigInt(value), BigInt(0)).toString();
}

export function toCsv(items: Material[], currency: Currency, tenderCode: string, company: string): string {
  const errors = validate(items);
  if (errors.length) throw new Error(errors[0]);
  const cell = (value: string) => {
    const safe = /^[\s]*[=+@-]/.test(value) || /^[\t\r\n]/.test(value) ? "'" + value : value;
    return `"${safe.replaceAll('"', '""')}"`;
  };
  const rows = [
    ["Licitación", "Empresa", "Moneda", "Descripción", "Unidad", "Cantidad", "Precio unitario", "Subtotal", "Total cotización"],
    ...items.map(item => [tenderCode, company, currency, item.description.trim(), item.unit.trim(), formatInteger(item.quantity), formatInteger(item.unit_price), formatInteger(subtotal(item)), formatInteger(total(items))]),
  ];
  return "\uFEFF" + rows.map(row => row.map(cell).join(";")).join("\r\n");
}
