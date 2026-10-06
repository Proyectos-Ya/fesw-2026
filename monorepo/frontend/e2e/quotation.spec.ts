import { expect, test } from "@playwright/test";
import type { Quotation } from "../src/features/quotations/quotation";
import { total } from "../src/features/quotations/quotation";
import { readFile } from "node:fs/promises";

test("crear, guardar, recuperar, editar y descargar materiales", async ({ page }, testInfo) => {
  let saved: Quotation | null = null;
  await page.route("**/api/tenders/*/quotation", async route => {
    if (route.request().method() === "PUT") {
      const body = route.request().postDataJSON() as Pick<Quotation, "items" | "currency">;
      saved = { ...body, id: "quote", supplier_id: "company", tender_id: "tender", updated_at: new Date().toISOString(), total: total(body.items) };
    }
    await route.fulfill({ status: saved ? 200 : 404, json: saved ?? { detail: "No existe" } });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Generar cotización" }).click();
  await page.getByRole("button", { name: "Guardar cotización" }).click();
  await expect(page.getByRole("alert")).toContainText("precio");
  await expect(page.getByLabel("Descripción 1", { exact: true })).toHaveValue("Cemento");
  await expect(page.getByLabel("Moneda", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("Unidad 1", { exact: true })).toHaveValue("saco");
  await expect(page.getByLabel("Cantidad 1", { exact: true })).toHaveValue("2");
  await page.getByLabel("Cantidad 1", { exact: true }).fill("2.5");
  await page.getByRole("button", { name: "Descargar PDF" }).click();
  await expect(page.getByRole("alert")).toContainText("entero");
  await page.getByLabel("Cantidad 1", { exact: true }).fill("2");
  await page.getByLabel("Precio unitario 1", { exact: true }).fill("100");
  await expect(page.getByLabel("Subtotal 1")).toHaveText("Subtotal: 200 CLP");
  await page.getByRole("button", { name: "Guardar cotización" }).click();
  await expect(page.getByText("Cotización guardada.", { exact: true })).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "Generar cotización" }).click();
  await expect(page.getByLabel("Descripción 1", { exact: true })).toHaveValue("Cemento");
  await page.getByLabel("Cantidad 1", { exact: true }).fill("3");
  await page.getByRole("button", { name: "Agregar material" }).click();
  await page.getByLabel("Eliminar material 2").click();
  const downloadEvent = page.waitForEvent("download");
  await page.getByRole("button", { name: "Descargar CSV" }).click();
  const download = await downloadEvent;
  expect(download.suggestedFilename()).toBe("cotizacion-227-15-COT26.csv");
  const file = await download.path();
  expect(await readFile(file!, "utf8")).toContain("300");
  expect(await readFile(file!, "utf8")).toContain("Cemento");
  expect(await readFile(file!, "utf8")).toContain('"Unidad"');
  expect(await readFile(file!, "utf8")).toContain('"saco"');
  await expect(page.getByText("Cotización guardada y descargada.", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  const pdfEvent = page.waitForEvent("download");
  await page.getByRole("button", { name: "Descargar PDF" }).click();
  const pdf = await pdfEvent;
  expect(pdf.suggestedFilename()).toBe("cotizacion-227-15-COT26.pdf");
  await pdf.saveAs(testInfo.outputPath("quotation.pdf"));
  expect((await readFile((await pdf.path())!)).subarray(0, 5).toString()).toBe("%PDF-");
  await page.screenshot({ path: testInfo.outputPath("quotation.png"), fullPage: true });
});

test("descarga PDF de 200 materiales con descripciones largas", async ({ page }, testInfo) => {
  const items = Array.from({length: 200}, (_, index) => ({description: `Material ${index + 1}: Hormigón, áridos y cañerías. ` + "Especificación técnica con instalación y revisión. ".repeat(7), unit: "unidad", quantity: "2", unit_price: "100"}));
  const saved = {id: "quote", supplier_id: "company", tender_id: "tender", currency: "CLP", updated_at: "2026-10-06T12:00:00Z", items, total: total(items)};
  await page.route("**/api/tenders/*/quotation", route => route.fulfill({json: saved}));
  await page.goto("/");
  await page.getByRole("button", {name: "Generar cotización"}).click();
  await expect(page.getByLabel("Descripción 200", {exact: true})).toBeAttached();
  const downloadEvent = page.waitForEvent("download");
  await page.getByRole("button", {name: "Descargar PDF"}).click();
  const download = await downloadEvent;
  await download.saveAs(testInfo.outputPath("quotation-long.pdf"));
  const text = (await readFile((await download.path())!)).toString("latin1");
  expect(text).toContain("Material 200");
  expect(text).toContain("40.000 CLP");
});
