import { expect, test } from "@playwright/test";

/**
 * El guardia de borde volvió (PENDIENTES 3.9) y esto lo fija.
 *
 * Antes estaba desactivado porque miraba una cookie que el borde de Vercel no
 * podía ver, y devolvía al login a quien acababa de entrar. La sesión de
 * Supabase vive en el origen del propio frontend, así que ahora sí decide, y
 * conviene que un test lo note si alguien lo vuelve a apagar.
 */
test("una ruta protegida sin sesión manda al login conservando el destino", async ({
  page,
}) => {
  await page.goto("/matches");

  await expect(page).toHaveURL(/\/login\?next=%2Fmatches/);
});

test("la raíz sin sesión manda al login sin parámetro sobrante", async ({ page }) => {
  await page.goto("/");

  await expect(page).toHaveURL(/\/login$/);
});

test("el login ofrece correo y Google", async ({ page }) => {
  await page.goto("/login");

  await expect(page.getByRole("button", { name: /iniciar sesión/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /continuar con google/i })).toBeVisible();
});

test("el registro lleva a la pantalla de verificación", async ({ page }) => {
  await page.goto("/verificar?email=persona%40ejemplo.cl");

  await expect(page.getByText(/revisa tu correo/i)).toBeVisible();
  await expect(page.getByText("persona@ejemplo.cl")).toBeVisible();
});
