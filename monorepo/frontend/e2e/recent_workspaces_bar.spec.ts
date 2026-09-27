import { test, expect } from "@playwright/test";

test.describe("Barra de Espacios de Trabajo Recientes en Inicio", () => {
  test("Muestra los workspaces recientes en el inicio y permite conmutar entre ellos", async ({ page }) => {
    // Iniciar sesión con multi@chiripa.cl
    await page.goto("/login");
    await page.fill('input[type="email"]', "multi@chiripa.cl");
    await page.fill('input[type="password"]', "Password123!");
    await page.click('button[type="submit"]');

    await expect(page).toHaveURL(/\/(|matches)$/, { timeout: 10000 });

    // Navegar al Inicio
    await page.goto("/");

    // 1. Verificar presencia de la barra de espacios de trabajo recientes
    const recentBar = page.getByText(/Espacios de trabajo recientes/i);
    await expect(recentBar).toBeVisible({ timeout: 10000 });

    // 2. Verificar que las empresas asociadas a multi@chiripa.cl aparecen en la barra principal
    const main = page.getByRole("main");
    const gammaButton = main.locator('button', { hasText: 'Gamma' });
    const otherButton = main.locator('button', { hasText: 'Alfa' });
    await expect(gammaButton).toBeVisible();
    await expect(otherButton).toBeVisible();

    // 3. Verificar que Gamma está marcada inicialmente como 'Activo'
    await expect(gammaButton.getByText(/Activo/i)).toBeVisible();

    // 4. Conmutar a Alfa haciendo clic en su tarjeta
    await otherButton.click();

    // 5. Esperar la recarga y verificar que ahora Alfa es la Activa
    await page.waitForTimeout(2500);
    const updatedAlfaButton = page.getByRole("main").locator('button', { hasText: 'Alfa' });
    await expect(updatedAlfaButton.getByText(/Activo/i)).toBeVisible({ timeout: 10000 });
  });
});
