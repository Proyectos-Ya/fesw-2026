import { describe, expect, it } from "vitest";
import {
  esDeclaracionDeHabilidad,
  basesNotice,
  canGenerate,
  currentAnswer,
  pauseOrigin,
  pausedRequirement,
  pendingRequirements,
  proposalStatus,
  questionFor,
  requirementsToReanswer,
} from "../proposal";
import type { DiscrepancyDecision, DraftContent } from "../../types";
import { SEC, SEC_NEGATIVA, VIALES, requisito, respuesta, vista } from "../../testing/fixtures";

describe("pendingRequirements", () => {
  it("son las que esperan una respuesta", () => {
    expect(pendingRequirements(vista()).map((r) => r.id)).toEqual(["req-1", "req-2"]);
  });
});

describe("canGenerate", () => {
  it("no con preguntas pendientes", () => {
    expect(canGenerate(vista())).toBe(false);
  });

  it("sí con todo respondido", () => {
    const v = vista({
      requirements: [requisito({ status: "cumple" }), requisito({ id: "r2", status: "parcial" })],
    });
    expect(canGenerate(v)).toBe(true);
  });

  it("no con una excluyente en No sin decisión de continuar", () => {
    const v = vista({ requirements: [requisito({ status: "no_cumple" })] });
    expect(canGenerate(v)).toBe(false);
  });

  it("sí si se decidió continuar con advertencia", () => {
    const v = vista({
      requirements: [requisito({ status: "no_cumple" })],
      discrepancy_decisions: [
        {
          requirement_id: "req-1",
          capability_question_id: SEC.id,
          action: "continue",
          user_id: "u-1",
          decided_at: "2026-10-01T12:00:00Z",
        },
      ],
    });
    expect(canGenerate(v)).toBe(true);
  });

  it("no en pausa, detenido ni vencido", () => {
    const listo = { requirements: [requisito({ status: "cumple" })] };
    expect(canGenerate(vista({ ...listo, status: "PAUSED" }))).toBe(false);
    expect(canGenerate(vista({ ...listo, status: "STOPPED" }))).toBe(false);
    expect(canGenerate(vista({ ...listo, is_expired: true }))).toBe(false);
  });
});

describe("questionFor", () => {
  it("encuentra la pregunta de la exigencia", () => {
    expect(questionFor(vista(), requisito())?.question).toBe(SEC.question);
  });

  it("null si la exigencia no tiene pregunta", () => {
    expect(questionFor(vista(), requisito({ capability_question_id: null }))).toBeNull();
  });
});

describe("pausa", () => {
  const pausada = vista({
    status: "PAUSED",
    paused_requirement_id: "req-1",
    requirements: [requisito({ status: "no_cumple", catalog_item_id: SEC_NEGATIVA.id })],
    catalog_items: [SEC_NEGATIVA],
  });

  it("encuentra la exigencia pausada", () => {
    expect(pausedRequirement(pausada)?.id).toBe("req-1");
    expect(pausedRequirement(vista())).toBeNull();
  });

  it("explica que el No viene de una respuesta anterior en otra licitación", () => {
    expect(pauseOrigin(pausada)).toEqual({
      answeredAt: "2026-09-12T15:00:00Z",
      fromAnotherTender: true,
    });
  });

  it("sin respuesta anterior no hay origen que explicar", () => {
    const recien = vista({
      status: "PAUSED",
      paused_requirement_id: "req-1",
      requirements: [requisito({ status: "no_cumple" })],
    });
    expect(pauseOrigin(recien)).toBeNull();
  });
});

function decision(action: DiscrepancyDecision["action"], requirementId = "req-1"): DiscrepancyDecision {
  return {
    requirement_id: requirementId,
    capability_question_id: SEC.id,
    action,
    user_id: "u-1",
    decided_at: "2026-10-01T12:00:00Z",
  };
}

const CONTENIDO: DraftContent = {
  offer_name: { paragraphs: [] },
  offer_description: { paragraphs: [] },
  required_documents: { paragraphs: [] },
  technical_document: null,
};

describe("requirementsToReanswer", () => {
  it("tras detener y reanudar, la excluyente detenida se vuelve a responder", () => {
    const v = vista({
      requirements: [requisito({ status: "no_cumple" })],
      discrepancy_decisions: [decision("stop")],
    });
    expect(requirementsToReanswer(v).map((r) => r.id)).toEqual(["req-1"]);
  });

  it("no incluye la que se decidió continuar con advertencia", () => {
    const v = vista({
      requirements: [requisito({ status: "no_cumple" })],
      discrepancy_decisions: [decision("stop"), decision("continue")],
    });
    expect(requirementsToReanswer(v)).toEqual([]);
  });

  it("en pausa o detenida no hay nada que responder de nuevo", () => {
    const base = {
      requirements: [requisito({ status: "no_cumple" })],
      discrepancy_decisions: [decision("stop")],
    };
    expect(requirementsToReanswer(vista({ ...base, status: "STOPPED" }))).toEqual([]);
    expect(
      requirementsToReanswer(vista({ ...base, status: "PAUSED", paused_requirement_id: "req-1" })),
    ).toEqual([]);
  });
});

describe("proposalStatus", () => {
  it("con preguntas pendientes dice cuántas faltan (informativo)", () => {
    const estado = proposalStatus(vista());
    expect(estado).toMatchObject({ tone: "info", title: "Faltan 2 respuestas", action: null });
    expect(estado?.detail).toMatch(/Responde las preguntas/);
  });

  it("en pausa bloquea, nombra la exigencia y ofrece revisarla", () => {
    const estado = proposalStatus(
      vista({
        status: "PAUSED",
        paused_requirement_id: "req-1",
        requirements: [requisito({ status: "no_cumple" })],
      }),
    );
    expect(estado).toMatchObject({ tone: "danger", title: "Postulación en pausa", action: "review" });
    expect(estado?.detail).toContain('exigencia excluyente "Deberá contar con certificación SEC"');
  });

  it("detenida bloquea y ofrece reanudar", () => {
    const estado = proposalStatus(
      vista({
        status: "STOPPED",
        requirements: [requisito({ status: "no_cumple" })],
        discrepancy_decisions: [decision("stop")],
      }),
    );
    expect(estado).toMatchObject({ tone: "danger", title: "Postulación detenida", action: "resume" });
    expect(estado?.detail).toMatch(/responde de nuevo/i);
  });

  it("reanudada con la excluyente en No pide responderla de nuevo (revisar)", () => {
    const estado = proposalStatus(
      vista({
        requirements: [requisito({ status: "no_cumple" })],
        discrepancy_decisions: [decision("stop")],
      }),
    );
    expect(estado).toMatchObject({ tone: "warning", action: null });
    expect(estado?.title).toMatch(/Responde de nuevo/);
    expect(estado?.detail).toContain('exigencia excluyente "Deberá contar con certificación SEC"');
  });

  it("con todo respondido está lista para redactar", () => {
    const estado = proposalStatus(vista({ requirements: [requisito({ status: "cumple" })] }));
    expect(estado).toMatchObject({ tone: "info", title: "Lista para redactar", action: null });
    expect(estado?.detail).toMatch(/Redactar borrador/);
  });

  it("lista pero con una excluyente aceptada con advertencia", () => {
    const estado = proposalStatus(
      vista({
        requirements: [requisito({ status: "no_cumple" })],
        discrepancy_decisions: [decision("continue")],
      }),
    );
    expect(estado).toMatchObject({ tone: "warning", title: "Lista para redactar, con advertencia" });
  });

  it("con el borrador listo y advertencias pide revisarlas", () => {
    const estado = proposalStatus(
      vista({
        status: "READY",
        content: CONTENIDO,
        requirements: [requisito({ status: "cumple" })],
        warnings: [{ requirement_id: "req-1", text: "No se cumple SEC." }],
      }),
    );
    expect(estado).toMatchObject({ tone: "warning", title: "Borrador listo, con advertencias" });
  });

  it("con el borrador listo y sin advertencias no hay nada que decir", () => {
    const v = vista({
      status: "READY",
      content: CONTENIDO,
      requirements: [requisito({ status: "cumple" })],
    });
    expect(proposalStatus(v)).toBeNull();
  });

  it("vencida no muestra estado: ya lo dice el aviso de licitación cerrada", () => {
    expect(proposalStatus(vista({ is_expired: true }))).toBeNull();
  });
});

describe("basesNotice", () => {
  it("borradores anteriores a este dato no dicen nada", () => {
    expect(basesNotice(vista({ analysis_documents: null }), [])).toBeNull();
  });

  it("analizado solo con la ficha recomienda subir las bases", () => {
    const v = vista({ content: CONTENIDO, analysis_documents: [], mentions_attachments: false });
    expect(basesNotice(v, [])).toBe(
      "Este borrador se hizo solo con la ficha. Si la Compra Ágil tiene bases, súbelas y vuelve a analizar.",
    );
  });

  it("si la ficha menciona bases que no se subieron, lo dice", () => {
    const v = vista({ content: CONTENIDO, analysis_documents: [], mentions_attachments: true });
    expect(basesNotice(v, [])).toMatch(/la ficha menciona bases o anexos que no se subieron/);
  });

  it("con archivos subidos después del análisis pide volver a analizar", () => {
    const v = vista({
      analysis_documents: [{ name: "bases.pdf", corrupted: false }],
      mentions_attachments: true,
    });
    expect(basesNotice(v, ["bases.pdf", "anexo.pdf"])).toBe(
      "Subiste archivos después del análisis. Vuelve a analizar para usarlos.",
    );
  });

  it("analizado con todas las bases subidas no dice nada", () => {
    const v = vista({ analysis_documents: [{ name: "bases.pdf", corrupted: false }] });
    expect(basesNotice(v, ["bases.pdf"])).toBeNull();
  });

  it("avisa los archivos que no se pudieron leer", () => {
    const v = vista({ analysis_documents: [{ name: "bases.pdf", corrupted: true }] });
    expect(basesNotice(v, ["bases.pdf"])).toMatch(/No se pudo leer bases.pdf/);
  });
});

describe("currentAnswer", () => {
  it("es el ítem capacidad:<pregunta> del catálogo", () => {
    const view = vista({ catalog_items: [respuesta(VIALES, "Sí"), SEC_NEGATIVA] });

    expect(currentAnswer(view, SEC.id)).toBe(SEC_NEGATIVA);
    expect(currentAnswer(view, VIALES.id)?.detail).toBe("Sí");
  });

  it("sin respuesta en el catálogo es null", () => {
    expect(currentAnswer(vista(), SEC.id)).toBeNull();
  });
});

describe("esDeclaracionDeHabilidad", () => {
  it("reconoce la declaración que se acepta al enviar", () => {
    expect(esDeclaracionDeHabilidad("Declaración Jurada de Habilidad")).toBe(true);
    expect(esDeclaracionDeHabilidad("adjuntar declaracion jurada de habilidad firmada")).toBe(true);
  });

  it("no confunde otros documentos", () => {
    expect(esDeclaracionDeHabilidad("Declaración jurada simple")).toBe(false);
    expect(esDeclaracionDeHabilidad("Cotización formal")).toBe(false);
  });
});
