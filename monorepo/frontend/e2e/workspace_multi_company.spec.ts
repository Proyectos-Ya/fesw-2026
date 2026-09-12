import { test, expect } from "@playwright/test";

test.describe("HdU 14: Asociación a distintas empresas con el mismo perfil (3 Pestañas / Contextos E2E)", () => {
  const password = "Password123!";

  test("Valida los 5 Criterios de Aceptación (CA-1 al CA-5) en simultáneo con 3 pestañas", async ({
    browser,
  }) => {
    test.setTimeout(90000);

    // ══════════════════════════════════════════════════════════════════
    // SETUP: 3 Pestañas / Contextos independientes de navegador
    // ══════════════════════════════════════════════════════════════════
    const contextAdmin = await browser.newContext();
    const contextInvited = await browser.newContext();
    const contextMulti = await browser.newContext();

    const pageAdmin = await contextAdmin.newPage(); // Pestaña 1: Admin Alfa (Carlos)
    const pageInvited = await contextInvited.newPage(); // Pestaña 2: Usuario Invitado (Ignacio)
    const pageMulti = await contextMulti.newPage(); // Pestaña 3: Usuario Multi-Empresa (Manuel)

    // Función auxiliar de login
    const loginUser = async (page, email: string) => {
      await page.goto("/login");
      await page.fill('input[type="email"]', email);
      await page.fill('input[type="password"]', password);
      await page.click('button[type="submit"]');
      await page.waitForURL((url) => !url.pathname.includes("/login"), {
        timeout: 15000,
      });
    };

    // ──────────────────────────────────────────────────────────────────
    // 1. INICIAR SESIÓN EN LAS 3 PESTAÑAS
    // ──────────────────────────────────────────────────────────────────
    await loginUser(pageAdmin, "admin1@chiripa.cl");
    await loginUser(pageInvited, "invitado@chiripa.cl");
    await loginUser(pageMulti, "multi@chiripa.cl");

    // ──────────────────────────────────────────────────────────────────
    // CA-1: Invitación in-app y aceptación sin crear nuevo perfil
    // ──────────────────────────────────────────────────────────────────
    // Pestaña 1 (Admin): Abrir modal de invitar miembro en Empresa Alfa
    await pageAdmin.click('button[aria-label="Seleccionar espacio de trabajo"]');
    await pageAdmin.click('button:has-text("Invitar miembro")');
    await expect(
      pageAdmin.getByRole("heading", { name: "Invitar miembro" }),
    ).toBeVisible();

    await pageAdmin.fill("#invite-email", "invitado@chiripa.cl");
    await pageAdmin.selectOption("#invite-role", "member");
    await pageAdmin.click('button[type="submit"]:has-text("Invitar miembro")');
    await expect(pageAdmin.getByText(/Invitación enviada con éxito/i)).toBeVisible();

    // Pestaña 2 (Invitado): Va a /alertas y ve la invitación pendiente
    await pageInvited.goto("/alertas");
    await expect(
      pageInvited.getByText(/Invitación para unirte como/i),
    ).toBeVisible();
    await expect(pageInvited.getByText(/Miembro/i)).toBeVisible();

    // Aceptar la invitación
    await pageInvited.click('button:has-text("Aceptar invitación")');
    await pageInvited.waitForTimeout(1000);

    // Verificar en Pestaña 2 que el usuario ahora tiene acceso a Empresa Alfa
    await pageInvited.click('button[aria-label="Seleccionar espacio de trabajo"]');
    await expect(
      pageInvited
        .locator('button[aria-label="Seleccionar espacio de trabajo"]')
        .getByText("Alfa"),
    ).toBeVisible();

    // ──────────────────────────────────────────────────────────────────
    // CA-2: Selección de espacio de trabajo al ingresar con múltiples empresas
    // ──────────────────────────────────────────────────────────────────
    // Pestaña 3 (Multi-Empresa): Navega a /workspaces
    await pageMulti.goto("/workspaces");
    await expect(
      pageMulti.getByRole("heading", {
        name: "Selecciona tu espacio de trabajo",
      }),
    ).toBeVisible();
    await expect(pageMulti.getByRole("button", { name: /Gamma/i })).toBeVisible();
    await expect(pageMulti.getByRole("button", { name: /Alfa/i })).toBeVisible();

    // ──────────────────────────────────────────────────────────────────
    // CA-3: Conmutación de espacio de trabajo y recálculo de roles y permisos
    // ──────────────────────────────────────────────────────────────────
    // En Pestaña 3: Selecciona Alfa (donde tiene rol Miembro)
    await pageMulti.getByRole("button", { name: /Alfa.*Miembro/i }).click();
    await expect(pageMulti).toHaveURL("/", { timeout: 10000 });

    // Verificar que en Alfa el rol visible es "Miembro"
    await expect(
      pageMulti
        .locator('button[aria-label="Seleccionar espacio de trabajo"]')
        .getByText("Miembro"),
    ).toBeVisible();
    await pageMulti.click('button[aria-label="Seleccionar espacio de trabajo"]');
    // Como Miembro, NO debe tener la opción de "Invitar miembro"
    await expect(pageMulti.getByText("Invitar miembro")).not.toBeVisible();

    // Conmutar a Gamma (donde es Admin)
    await pageMulti.locator('button').filter({ hasText: /Gamma/i }).first().click();
    await pageMulti.waitForTimeout(1000);

    // Verificar que al conmutar a Gamma, ahora es "Admin" y SI puede invitar
    await expect(
      pageMulti
        .locator('button[aria-label="Seleccionar espacio de trabajo"]')
        .getByText("Admin"),
    ).toBeVisible();
    await pageMulti.click('button[aria-label="Seleccionar espacio de trabajo"]');
    await expect(pageMulti.getByText("Invitar miembro")).toBeVisible();

    // ──────────────────────────────────────────────────────────────────
    // CA-4: Aislamiento de contexto y datos según la empresa activa
    // ──────────────────────────────────────────────────────────────────
    // En Pestaña 3 con Gamma activa: La barra lateral muestra Gamma
    await expect(
      pageMulti
        .locator('button[aria-label="Seleccionar espacio de trabajo"]')
        .getByText("Gamma"),
    ).toBeVisible();

    // ──────────────────────────────────────────────────────────────────
    // CA-5: Registrar nueva empresa desde sesión existente (Rol Admin automático)
    // ──────────────────────────────────────────────────────────────────
    // En Pestaña 2 (Invitado): Va a crear una nueva empresa mediante el ProfileWizard
    await pageInvited.goto("/empresa/crear");

    // Paso 1: Identidad
    await pageInvited.fill('input[name="legal_name"]', "Empresa Delta SpA");
    await pageInvited.fill('input[name="trade_name"]', "Delta");
    await pageInvited.fill('input[name="rut"]', "79.444.444-7");
    await pageInvited.click('button:has-text("Siguiente")');

    // Paso 2: Operación
    await pageInvited.locator('button').filter({ hasText: /Metropolitana/i }).first().click();
    await pageInvited.fill('input[name="years_experience"]', "5");
    await pageInvited.fill('input[name="num_employees"]', "10");
    await pageInvited.click('button:has-text("Siguiente")');

    // Paso 3: Especialización
    await pageInvited.locator('button').filter({ hasText: /Tecnología|Construcción|Servicios/i }).first().click();
    await pageInvited.fill(
      'textarea[name="description"]',
      "Empresa dedicada a la prestación de servicios integrales para licitaciones públicas y privadas.",
    );
    await pageInvited.click('button:has-text("Siguiente")');

    // Paso 4: Resumen y confirmación
    await pageInvited.click('button:has-text("Guardar perfil y comenzar")');

    // Confirmación y redirección
    await expect(pageInvited.getByText("¡Perfil creado con éxito!")).toBeVisible({
      timeout: 15000,
    });
    await pageInvited.click('button:has-text("Ir a mi dashboard")');
    await expect(pageInvited).toHaveURL("/", { timeout: 15000 });
    await expect(
      pageInvited
        .locator('button[aria-label="Seleccionar espacio de trabajo"]')
        .getByText("Delta"),
    ).toBeVisible();
    await expect(
      pageInvited
        .locator('button[aria-label="Seleccionar espacio de trabajo"]')
        .getByText("Admin"),
    ).toBeVisible();

    // Cleanup de contextos
    await contextAdmin.close();
    await contextInvited.close();
    await contextMulti.close();
  });
});
