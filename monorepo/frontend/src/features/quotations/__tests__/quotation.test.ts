import { describe, expect, it } from "vitest";
import { subtotal, total, validate, toCsv } from "../quotation";

const item = { description: "Cemento", unit: "saco", quantity: "2.5", unit_price: "100.25" };

describe("cotización", () => {
  it("redondea cada subtotal con decimales exactos", () => {
    expect(subtotal(item)).toBe("250.63");
    expect(total([item, item])).toBe("501.26");
  });
  it("rechaza campos vacíos, cantidades no positivas y precios negativos", () => {
    expect(validate([])).not.toEqual([]);
    for (const change of [{ description: " " }, { unit: "" }, { quantity: "0" }, { quantity: "-1" }, { unit_price: "-1" }, { unit_price: "" }, { quantity: "Infinity" }]) {
      expect(validate([{ ...item, ...change }])).not.toEqual([]);
    }
    expect(validate([{ ...item, unit_price: "0" }])).toEqual([]);
  });
  it("exporta identificadores, moneda y totales; escapa texto y fórmulas", () => {
    const csv = toCsv([{ ...item, description: '=SUM(1,2)\n"prueba"' }], "CLP", "123-45", "Empresa");
    expect(csv).toContain("CLP");
    expect(csv).toContain("250.63");
    expect(csv).toContain("123-45");
    expect(csv).toContain("'=SUM(1,2)");
    expect(csv).toContain('""prueba""');
  });
});
