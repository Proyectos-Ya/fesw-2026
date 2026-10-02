import type { CapabilityQuestion, ProposalView, Requirement } from "../types";

/** Exigencias que esperan la respuesta de la empresa. */
export function pendingRequirements(view: ProposalView): Requirement[] {
  return view.requirements.filter((r) => r.status === "desconocido");
}

function decisionDe(view: ProposalView, requirementId: string) {
  return [...view.discrepancy_decisions]
    .reverse()
    .find((d) => d.requirement_id === requirementId);
}

/**
 * ¿Se puede redactar? La misma regla que `ProposalDraft.can_generate` del
 * backend (la "pausa" del CA7), para no ofrecer un botón que dará 409.
 */
export function canGenerate(view: ProposalView): boolean {
  if (view.is_expired) return false;
  if (view.status !== "FEASIBILITY" && view.status !== "READY") return false;
  if (pendingRequirements(view).length > 0) return false;
  return !view.requirements.some(
    (r) =>
      r.mandatory &&
      r.status === "no_cumple" &&
      decisionDe(view, r.id)?.action !== "continue",
  );
}

export function questionFor(
  view: ProposalView,
  requirement: Requirement,
): CapabilityQuestion | null {
  if (!requirement.capability_question_id) return null;
  return view.questions.find((q) => q.id === requirement.capability_question_id) ?? null;
}

export function pausedRequirement(view: ProposalView): Requirement | null {
  if (view.status !== "PAUSED" || !view.paused_requirement_id) return null;
  return view.requirements.find((r) => r.id === view.paused_requirement_id) ?? null;
}

export interface PauseOrigin {
  answeredAt: string;
  fromAnotherTender: boolean;
}

/**
 * Si la pausa la causó una respuesta anterior de la empresa (no una de ahora),
 * cuándo y si fue en otra licitación. Sirve para que el aviso no sorprenda.
 */
export function pauseOrigin(view: ProposalView): PauseOrigin | null {
  const requirement = pausedRequirement(view);
  if (!requirement?.catalog_item_id) return null;
  const item = view.catalog_items.find((i) => i.id === requirement.catalog_item_id);
  if (!item?.answered_at) return null;
  return {
    answeredAt: item.answered_at,
    fromAnotherTender: item.tender_id !== null && item.tender_id !== view.tender_id,
  };
}
