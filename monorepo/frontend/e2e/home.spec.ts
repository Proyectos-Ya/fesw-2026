import { test, expect } from '@playwright/test';

test('has title or main content', async ({ page }) => {
  await page.goto('/');
  
  // Verifica que el encabezado principal de la landing contenga la frase esperada
  await expect(page.locator('h1')).toContainText('To get started');
});
