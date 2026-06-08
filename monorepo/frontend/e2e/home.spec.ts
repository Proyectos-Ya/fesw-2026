import { test, expect } from '@playwright/test';

test('renders topbar with brand and login', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('ProyectosYa')).toBeVisible();
  await expect(page.getByRole('button', { name: /iniciar sesión/i })).toBeVisible();
});
