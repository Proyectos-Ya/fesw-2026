import { describe, expect, it } from "vitest";
import { subtotal, total, validate, toCsv, materialsFromTender, formatInteger } from "../quotation";

const item = { description: "Cemento", unit: "saco", quantity: "2", unit_price: "100" };

describe("cotización", () => {
  it("usa descripción o nombre y deja cantidad y precio pendientes", () => {
    expect(materialsFromTender([{ name: "Genérico", description: " Material específico ", unit_of_measure: "saco" }, { name: "Arena", description: null }, { name: " ", description: " " }])).toEqual([
      { description: "Material específico", unit: "saco", quantity: "", unit_price: "" },
      { description: "Arena", unit: "", quantity: "", unit_price: "" },
    ]);
  });
  it("calcula subtotales y total enteros exactos", () => {
    expect(subtotal(item)).toBe("200");
    expect(total([item, item])).toBe("400");
  });
  it("rechaza campos vacíos, cantidades no positivas y precios negativos", () => {
    expect(validate([])).not.toEqual([]);
    for (const change of [{ unit: "" }, { description: " " }, { quantity: "0" }, { quantity: "-1" }, { unit_price: "-1" }, { unit_price: "" }, { quantity: "Infinity" }, { quantity: "1.5" }, { unit_price: "10.5" }]) {
      expect(validate([{ ...item, ...change }])).not.toEqual([]);
    }
    expect(validate([{ ...item, unit_price: "0" }])).toEqual([]);
  });
  it("exporta identificadores, moneda y totales; escapa texto y fórmulas", () => {
    const csv = toCsv([{ ...item, description: '=SUM(1,2)\n"prueba"' }], "CLP", "123-45", "Empresa");
    expect(csv).toContain("CLP");
    expect(csv).toContain('"Unidad"');
    expect(csv).toContain("200");
    expect(csv).toContain("123-45");
    expect(csv).toContain("'=SUM(1,2)");
    expect(csv).toContain('""prueba""');
  });
});

it("precarga cantidades enteras sin redondear fracciones", () => {
  const items = materialsFromTender([2, 0, -1, 2.5, 999999999, 1000000000].map(quantity => ({name: "Arena", description: null, quantity})));
  expect(items.map(item => item.quantity)).toEqual(["2", "", "", "", "999999999", ""]);
});
it("mantiene precisión más allá de Number.MAX_SAFE_INTEGER", () => {
  expect(total([{ ...item, quantity: "999999999", unit_price: "999999999999" }])).toBe("999999998999000000001");
});

it("separa miles con puntos sin perder precisión", () => {
  expect(formatInteger("1250000")).toBe("1.250.000");
  expect(formatInteger("999999998999000000001")).toBe("999.999.998.999.000.000.001");
  expect(formatInteger("0")).toBe("0");
  expect(toCsv([{...item, quantity: "2000", unit_price: "1500"}], "CLP", "123", "empresa")).toContain('"2.000";"1.500";"3.000.000";"3.000.000"');
});
