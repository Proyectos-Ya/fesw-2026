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
  await expect(page.getByRole("alert")).toContainText("cantidad");
  await expect(page.getByLabel("Descripción 1", { exact: true })).toHaveValue("Cemento");
  await expect(page.getByLabel("Moneda", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("Unidad 1", { exact: true })).toHaveValue("saco");
  await page.getByLabel("Cantidad 1", { exact: true }).fill("2.5");
  await page.getByLabel("Precio unitario 1", { exact: true }).fill("100.25");
  await expect(page.getByLabel("Subtotal 1")).toHaveText("Subtotal: 250.63 CLP");
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
  expect(await readFile(file!, "utf8")).toContain("300.75");
  expect(await readFile(file!, "utf8")).toContain("Cemento");
  expect(await readFile(file!, "utf8")).toContain('"Unidad"');
  expect(await readFile(file!, "utf8")).toContain('"saco"');
  await expect(page.getByText("Cotización guardada y descargada.", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("quotation.png"), fullPage: true });
});
