// @vitest-environment node
import { describe, expect, it } from "vitest";
import { quotationPdf } from "../quotationPdf";
import type { Quotation } from "../quotation";
const quote: Quotation = {id: "q", supplier_id: "empresa", tender_id: "t", currency: "CLP", updated_at: "2026-10-06T12:00:00Z", total: "200", items: [{description: "Cemento", unit: "saco", quantity: "2", unit_price: "100"}]};
describe("PDF de cotizaciones", () => {
  it("genera un PDF con el detalle y total sin decimales", async () => {
    const blob = quotationPdf(quote, "227-15-COT26");
    expect(blob.type).toBe("application/pdf");
    const text = await blob.text();
    expect(text).toMatch(/^%PDF-/);
    for (const value of ["227-15-COT26", "empresa", "Cemento", "200 CLP"]) expect(text).toContain(value);
    expect(text).not.toContain("200.00");
  });
  it("pagina 200 materiales sin perder el último ni el total", async () => {
    const items = Array.from({length: 200}, (_, i) => ({...quote.items[0], description: `Material ${i + 1} ` + "Descripción extensa de material. ".repeat(8)}));
    const text = await quotationPdf({...quote, items, total: "40000"}, "227-15-COT26").text();
    expect((text.match(/\/Type \/Page\b/g) ?? []).length).toBeGreaterThan(1);
    expect(text).toContain("Material 200");
    expect(text).toContain("40000 CLP");
  });
  it("rechaza fracciones antes de exportar", () => {
    expect(() => quotationPdf({...quote, items: [{...quote.items[0], quantity: "2.5"}]}, "227")).toThrow(/entero/);
  });
});
