export interface Material {
  description: string;
  unit: string;
  quantity: string;
  unit_price: string;
}

export type Currency = "CLP" | "USD" | "EUR" | "UF";
export interface Quotation {
  id: string;
  supplier_id: string;
  tender_id: string;
  currency: Currency;
  items: Material[];
  total: string;
  updated_at: string;
}

function validDecimal(value: string, integers: number, decimals: number): boolean {
  return new RegExp(`^\\d{1,${integers}}(?:\\.\\d{1,${decimals}})?$`).test(value);
}

export function validate(items: Material[]): string[] {
  if (!items.length) return ["Agrega al menos un material."];
  if (items.length > 200) return ["Puedes agregar hasta 200 materiales."];
  return items.flatMap((item, index) => {
    const errors: string[] = [];
    const label = `Material ${index + 1}: `;
    if (!item.description.trim() || item.description.trim().length > 500) errors.push(label + "indica una descripción de hasta 500 caracteres.");
    if (!item.unit.trim() || item.unit.trim().length > 40) errors.push(label + "indica una unidad de hasta 40 caracteres.");
    if (!validDecimal(item.quantity, 9, 3) || Number(item.quantity) <= 0) errors.push(label + "la cantidad debe ser mayor que cero, con hasta 9 enteros y 3 decimales.");
    if (!validDecimal(item.unit_price, 12, 2)) errors.push(label + "el precio debe ser cero o positivo, con hasta 12 enteros y 2 decimales.");
    return errors;
  });
}

function scaled(value: string, places: number): bigint {
  const [whole, fraction = ""] = value.split(".");
  return BigInt(whole + fraction.padEnd(places, "0"));
}

function cents(item: Material): bigint {
  if (!validDecimal(item.quantity, 9, 3) || !validDecimal(item.unit_price, 12, 2)) return BigInt(0);
  return (scaled(item.quantity, 3) * scaled(item.unit_price, 2) + BigInt(500)) / BigInt(1000);
}

function money(value: bigint): string {
  return `${value / BigInt(100)}.${(value % BigInt(100)).toString().padStart(2, "0")}`;
}

export function subtotal(item: Material): string { return money(cents(item)); }
export function total(items: Material[]): string { return money(items.reduce((sum, item) => sum + cents(item), BigInt(0))); }

export function toCsv(items: Material[], currency: Currency, tenderCode: string, company: string): string {
  const errors = validate(items);
  if (errors.length) throw new Error(errors[0]);
  const cell = (value: string) => {
    const safe = /^[\s]*[=+@-]/.test(value) || /^[\t\r\n]/.test(value) ? "'" + value : value;
    return `"${safe.replaceAll('"', '""')}"`;
  };
  const rows = [
    ["Licitación", "Empresa", "Moneda", "Descripción", "Unidad", "Cantidad", "Precio unitario", "Subtotal", "Total cotización"],
    ...items.map(item => [tenderCode, company, currency, item.description.trim(), item.unit.trim(), item.quantity, item.unit_price, subtotal(item), total(items)]),
  ];
  return "\uFEFF" + rows.map(row => row.map(cell).join(";")).join("\r\n");
}
