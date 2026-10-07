import { expect, test, type Route } from "@playwright/test";
import type {
  DiscrepancyDecision,
  DraftContent,
  ExperienceItem,
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
    technical_document_ambiguous: null,
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

const VIALES_QUESTION = {
  ...SEC_QUESTION,
  id: "q-viales",
  question: "¿Tiene experiencia en obras viales?",
  target_field: "experiencia:obras-viales",
  kind: "experiencia_proyecto" as const,
  work_type: "obras viales",
};

function exigenciaViales(status: Requirement["status"]): Requirement {
  return {
    ...exigencia(status),
    id: "req-2",
    text: "Se valorará experiencia en obras viales.",
    kind: "experiencia",
    mandatory: false,
    capability_question_id: VIALES_QUESTION.id,
  };
}

function respuestaViales(detail: "Sí" | "No", tenderId: string): ExperienceItem {
  return {
    id: `capacidad:${VIALES_QUESTION.id}`,
    origin: "capacidad",
    kind: "experiencia_proyecto",
    title: VIALES_QUESTION.question,
    detail,
    polarity: detail === "Sí" ? "afirmativa" : "negativa",
    answered_by_user_id: "u-1",
    tender_id: tenderId,
    answered_at: "2026-09-12T15:00:00Z",
  };
}

test("con el borrador listo, cambiar una respuesta y agregar un proyecto", async ({ page }) => {
  let actual: ProposalView = borrador({
    status: "READY",
    content: {
      ...CONTENIDO,
      offer_description: {
        paragraphs: [{ text: "a".repeat(300), sources: [], placeholders: [] }],
      },
    },
    requirements: [exigencia("cumple"), exigenciaViales("no_cumple")],
    questions: [SEC_QUESTION, VIALES_QUESTION],
    // La respuesta "No" se dio en otra licitación.
    catalog_items: [respuestaViales("No", "t-otra")],
  });
  let proyecto: unknown = null;

  await page.route("**/api/tenders/t-1", (route) =>
    route.fulfill({
      json: {
        tender: { id: "t-1", code: "657-70-COT26", name: "Bacheo", items: [] },
        score_pct: null,
        is_closed: false,
      },
    }),
  );
  await page.route("**/api/tenders/t-1/assistant/documents", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/tenders/t-1/quotation", (route) =>
    route.fulfill({ status: 404, json: { detail: "No existe" } }),
  );
  await page.route("**/api/capabilities/questions/q-viales/evidence", (route) => {
    proyecto = route.request().postDataJSON();
    return route.fulfill({ status: 201, json: { id: "ev-1" } });
  });
  await page.route("**/api/tenders/t-1/proposal**", async (route: Route) => {
    const request = route.request();
    if (request.method() === "POST") {
      // Responder en READY deja el borrador listo y marca el texto desactualizado.
      actual = {
        ...actual,
        requirements: [exigencia("cumple"), exigenciaViales("cumple")],
        catalog_items: [respuestaViales("Sí", "t-1")],
        changed_requirement_ids: ["req-2"],
        updated_at: "2026-10-07T13:00:00Z",
      };
    }
    return route.fulfill({ json: actual });
  });

  await page.goto("/");

  // El detalle de la cotización cuenta los caracteres que acepta Mercado Público.
  const detalle = page.getByRole("region", { name: "Detalle de la cotización" });
  await expect(detalle).toContainText("300/255");
  await expect(detalle).toContainText("Supera los 255 caracteres");

  await page.getByText(/Ver exigencias evaluadas/).click();
  const evaluadas = page.getByRole("region", { name: "Exigencias evaluadas" });
  await evaluadas.getByRole("button", { name: "Cambiar respuesta" }).nth(1).click();
  await expect(evaluadas).toContainText(
    "en otra licitación. Cambiarla la actualiza para todas tus postulaciones.",
  );
  await expect(evaluadas.getByRole("button", { name: "No", exact: true })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await evaluadas.getByRole("button", { name: "Sí", exact: true }).click();

  await expect(page.getByText("Respuesta guardada.")).toBeVisible();
  await expect(page.getByText(/Cambiaron respuestas de tu empresa/)).toBeVisible();

  // Tras el "Sí" a una pregunta de proyectos se sugiere respaldarlo.
  const sugerencia = page.getByRole("status", { name: "Agregar un proyecto" });
  await sugerencia.getByRole("button", { name: "Agregar proyecto" }).click();
  const formulario = page.getByRole("dialog", { name: "Agregar proyecto" });
  await formulario.getByLabel("Título del proyecto").fill("Bacheo calle Prat");
  await formulario.getByLabel("Mandante").fill("Municipalidad de Pica");
  await formulario.getByLabel("Año").fill("2024");
  await formulario.getByLabel("Monto en CLP").fill("12.000.000");
  await formulario.getByRole("button", { name: "Guardar proyecto" }).click();

  await expect(page.getByText("Proyecto agregado. Se usará al redactar o regenerar.")).toBeVisible();
  await expect(formulario).toHaveCount(0);
  expect(proyecto).toEqual({
    title: "Bacheo calle Prat",
    buyer: "Municipalidad de Pica",
    year: 2024,
    amount_clp: 12_000_000,
    description: null,
  });
  await expect(sugerencia).toHaveCount(0);
  // El "Sí" vigente también se puede respaldar desde la lista.
  await expect(evaluadas.getByRole("button", { name: "Agregar proyecto" })).toBeVisible();
});

test("las bases mencionan un informe técnico sin aclarar si va con la cotización", async ({
  page,
}) => {
  // Caso de la Compra Ágil 1377068-65-COT26 (§2.8 del plan).
  const motivo =
    'Las bases dicen "Se debe entregar informe técnico y certificado individual por cada equipo" en las condiciones de ejecución, sin aclarar si va con la oferta.';
  let actual: ProposalView = borrador({
    status: "READY",
    content: CONTENIDO,
    requirements: [exigencia("cumple")],
    technical_document_ambiguous: true,
    technical_document_reason: motivo,
  });
  let pidioDocumento = false;

  await page.route("**/api/tenders/t-1", (route) =>
    route.fulfill({
      json: {
        tender: { id: "t-1", code: "1377068-65-COT26", name: "Mantención de extintores", items: [] },
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
    if (request.method() === "POST" && request.url().endsWith("/technical-document")) {
      pidioDocumento = true;
      actual = {
        ...actual,
        content: {
          ...CONTENIDO,
          technical_document: {
            sections: [
              {
                key: "metodologia",
                title: "Metodología",
                guidance: "Cómo se hará el trabajo, paso a paso.",
                hint: "Indica cómo emitirás el certificado de cada extintor.",
                paragraphs: [
                  { text: "Revisión y recarga de cada equipo.", sources: [], placeholders: [] },
                ],
              },
            ],
          },
        },
      };
    }
    return route.fulfill({ json: actual });
  });

  await page.goto("/");

  const bloque = page.getByRole("region", { name: "Documento técnico" });
  await expect(bloque).toContainText("Las bases mencionan un informe técnico");
  await expect(bloque).toContainText("Se debe entregar informe técnico y certificado individual");
  await expect(bloque).not.toContainText("No se detectó");
  await bloque.getByRole("button", { name: "Generar documento técnico" }).click();

  await expect(bloque).toContainText("Revisión y recarga de cada equipo.");
  await expect(bloque).toContainText("Qué poner: Cómo se hará el trabajo, paso a paso.");
  await expect(bloque).toContainText(
    "Para esta licitación: Indica cómo emitirás el certificado de cada extintor.",
  );
  expect(pidioDocumento).toBe(true);
});
