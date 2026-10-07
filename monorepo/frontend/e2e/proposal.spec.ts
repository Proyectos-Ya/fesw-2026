import { expect, test, type Route } from "@playwright/test";
import type {
  DiscrepancyDecision,
  DraftContent,
  ProposalView,
  Requirement,
} from "../src/features/proposals/types";

/**
 * Flujo de postulación con la API simulada (#292): iniciar sin bases, responder
 * "No" a una excluyente, detener, reanudar, responder de nuevo, redactar y
 * regenerar. El backend es un objeto en memoria que cambia con cada POST, con
 * las mismas reglas que `ProposalDraft` del backend para este caso.
 */

const SEC_QUESTION = {
  id: "q-sec",
  question: "¿Cuenta con certificación SEC vigente?",
  target_field: "sec",
  category: "servicios",
  kind: "certificacion" as const,
  work_type: null,
  options: [
    { label: "Sí", polarity: "afirmativa" as const },
    { label: "No", polarity: "negativa" as const },
  ],
};

const CONTENIDO: DraftContent = {
  offer_name: { paragraphs: [{ text: "Capacitación PAC", sources: [], placeholders: [] }] },
  offer_description: {
    paragraphs: [{ text: "Somos instaladores con SEC vigente.", sources: [], placeholders: [] }],
  },
  required_documents: { paragraphs: [] },
  technical_document: null,
};

function exigencia(status: Requirement["status"]): Requirement {
  return {
    id: "req-1",
    text: "Deberá contar con certificación SEC.",
    kind: "certificacion",
    mandatory: true,
    origin: "Descripción",
    status,
    catalog_item_id: null,
    capability_question_id: SEC_QUESTION.id,
    suggested: false,
  };
}

function decision(action: DiscrepancyDecision["action"]): DiscrepancyDecision {
  return {
    requirement_id: "req-1",
    capability_question_id: SEC_QUESTION.id,
    action,
    user_id: "u-1",
    decided_at: "2026-10-07T12:00:00Z",
  };
}

function borrador(overrides: Partial<ProposalView>): ProposalView {
  return {
    id: "p-1",
    supplier_id: "s-1",
    tender_id: "t-1",
    status: "FEASIBILITY",
    requirements: [exigencia("desconocido")],
    paused_requirement_id: null,
    requires_technical_document: false,
    technical_document_reason: null,
    warnings: [],
    discrepancy_decisions: [],
    content: null,
    last_instructions: null,
    created_by_user_id: "u-1",
    created_at: "2026-10-07T12:00:00Z",
    updated_at: "2026-10-07T12:00:00Z",
    is_expired: false,
    questions: [SEC_QUESTION],
    catalog_items: [],
    changed_requirement_ids: [],
    analysis_documents: [],
    mentions_attachments: true,
    ...overrides,
  };
}

test("postular sin bases, detener, reanudar, responder de nuevo y regenerar", async ({ page }) => {
  let actual: ProposalView | null = null;
  let soltarRegeneracion: () => void = () => {};
  const regeneracion = new Promise<void>((resolve) => (soltarRegeneracion = resolve));

  await page.route("**/api/tenders/t-1", (route) =>
    route.fulfill({
      json: {
        tender: { id: "t-1", code: "657-70-COT26", name: "Instalación eléctrica", items: [] },
        score_pct: null,
        is_closed: false,
      },
    }),
  );
  await page.route("**/api/tenders/t-1/assistant/documents", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/tenders/t-1/quotation", (route) =>
    route.fulfill({ status: 404, json: { detail: "No existe" } }),
  );
  await page.route("**/api/tenders/t-1/proposal**", async (route: Route) => {
    const request = route.request();
    const accion = new URL(request.url()).pathname.replace("/api/tenders/t-1/proposal", "");
    if (request.method() === "GET") {
      return actual
        ? route.fulfill({ json: actual })
        : route.fulfill({ status: 404, json: { detail: "No hay postulación" } });
    }
    if (accion === "/feasibility") {
      actual = borrador({});
    } else if (accion.startsWith("/questions/")) {
      const { answer } = request.postDataJSON() as { answer: string };
      actual =
        answer === "No"
          ? borrador({
              status: "PAUSED",
              paused_requirement_id: "req-1",
              requirements: [exigencia("no_cumple")],
              discrepancy_decisions: [],
            })
          : borrador({ requirements: [exigencia("cumple")], discrepancy_decisions: [] });
    } else if (accion === "/discrepancy") {
      actual = borrador({
        status: "STOPPED",
        requirements: [exigencia("no_cumple")],
        discrepancy_decisions: [decision("stop")],
      });
    } else if (accion === "/resume") {
      actual = borrador({ ...actual, status: "FEASIBILITY", paused_requirement_id: null });
    } else if (accion === "/generate") {
      actual = borrador({ ...actual, status: "READY", content: CONTENIDO });
    } else if (accion === "/regenerate") {
      await regeneracion;
      actual = borrador({ ...actual, last_instructions: "Más formal" });
    }
    return route.fulfill({ json: actual });
  });

  await page.goto("/");

  // Sin bases se puede iniciar, con una recomendación informativa.
  await expect(page.getByText(/No has subido bases/)).toBeVisible();
  await page.getByRole("button", { name: "Iniciar análisis" }).click();

  const banner = page.getByRole("region", { name: "Estado de la postulación" });
  await expect(banner).toContainText("Falta 1 respuesta");

  // Un "No" a la excluyente pausa y abre el aviso.
  const pendientes = page.getByRole("region", { name: /Preguntas por responder/ });
  await pendientes.getByRole("button", { name: "No" }).click();
  await expect(page.getByText("Respuesta guardada.")).toBeVisible();
  const aviso = page.getByRole("dialog");
  await expect(aviso).toContainText("Recomendamos no postular");
  await aviso.getByRole("button", { name: "Detener postulación" }).click();

  await expect(banner).toContainText("Postulación detenida");
  await banner.getByRole("button", { name: "Reanudar" }).click();

  // Tras reanudar, la exigencia que la detuvo se responde de nuevo.
  await expect(banner).toContainText("Responde de nuevo");
  const deNuevo = page.getByRole("region", { name: /Responder de nuevo/ });
  await deNuevo.getByRole("button", { name: "Sí" }).click();

  await expect(banner).toContainText("Lista para redactar");
  await page.getByRole("button", { name: "Redactar borrador" }).click();

  const seccionBorrador = page.getByRole("region", { name: "Borrador de la oferta" });
  await expect(seccionBorrador).toContainText("Capacitación PAC");
  await expect(seccionBorrador).toContainText("Este borrador se hizo solo con la ficha");

  // Regenerar: capa de carga, botón con spinner y aviso de etapa a la vista.
  await page.getByRole("button", { name: "Regenerar" }).click();
  await page.getByRole("dialog").getByRole("textbox").fill("Más formal");
  await page.getByRole("dialog").getByRole("button", { name: "Regenerar" }).click();

  await expect(page.getByTestId("capa-de-carga")).toBeVisible();
  await expect(page.getByRole("button", { name: "Regenerar" })).toHaveAttribute("aria-busy", "true");
  const etapa = page.getByRole("status").filter({ hasText: "Regenerando el borrador con tus instrucciones" });
  await page.mouse.wheel(0, 5000);
  await expect(etapa).toBeInViewport();

  soltarRegeneracion();
  await expect(page.getByTestId("capa-de-carga")).toHaveCount(0);
  await expect(page.getByText("Borrador regenerado con tus instrucciones.")).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBe(true);
});
