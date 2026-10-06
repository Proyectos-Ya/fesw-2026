import { describe, expect, it } from "vitest";
import {
  canGenerate,
  pauseOrigin,
  pausedRequirement,
  pendingRequirements,
  questionFor,
} from "../proposal";
import { SEC, SEC_NEGATIVA, requisito, vista } from "../../testing/fixtures";

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
