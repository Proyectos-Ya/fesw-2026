import type {
  CapabilityQuestion,
  ExperienceItem,
  ProposalView,
  Requirement,
} from "../types";

export const SEC: CapabilityQuestion = {
  id: "q-sec",
  question: "¿Cuenta con certificación SEC vigente?",
  target_field: "sec",
  category: "servicios",
  kind: "certificacion",
  work_type: null,
  options: [
    { label: "Sí", polarity: "afirmativa" },
    { label: "No", polarity: "negativa" },
  ],
};

export const VIALES: CapabilityQuestion = {
  ...SEC,
  id: "q-viales",
  question: "¿Tiene experiencia en obras viales?",
  target_field: "experiencia:obras-viales",
  kind: "experiencia_proyecto",
  work_type: "obras viales",
};

export function requisito(overrides: Partial<Requirement> = {}): Requirement {
  return {
    id: "req-1",
    text: "Deberá contar con certificación SEC.",
    kind: "certificacion",
    mandatory: true,
    origin: "Descripción",
    status: "desconocido",
    catalog_item_id: null,
    capability_question_id: SEC.id,
    suggested: false,
    ...overrides,
  };
}

export const SEC_NEGATIVA: ExperienceItem = {
  id: `capacidad:${SEC.id}`,
  origin: "capacidad",
  kind: "certificacion",
  title: SEC.question,
  detail: "No",
  polarity: "negativa",
  answered_by_user_id: "u-ana",
  tender_id: "t-otra",
  answered_at: "2026-09-12T15:00:00Z",
};

/** La respuesta vigente de la empresa a una pregunta, como la trae el catálogo. */
export function respuesta(
  pregunta: CapabilityQuestion,
  detail: string,
  overrides: Partial<ExperienceItem> = {},
): ExperienceItem {
  const opcion = pregunta.options.find((o) => o.label === detail);
  return {
    id: `capacidad:${pregunta.id}`,
    origin: "capacidad",
    kind: pregunta.kind,
    title: pregunta.question,
    detail,
    polarity: opcion?.polarity ?? null,
    answered_by_user_id: "u-1",
    tender_id: "t-1",
    answered_at: "2026-10-01T12:00:00Z",
    ...overrides,
  };
}

export function vista(overrides: Partial<ProposalView> = {}): ProposalView {
  return {
    id: "p-1",
    supplier_id: "s-1",
    tender_id: "t-1",
    status: "FEASIBILITY",
    requirements: [
      requisito(),
      requisito({
        id: "req-2",
        text: "Se valorará experiencia en obras viales.",
        kind: "experiencia",
        mandatory: false,
        capability_question_id: VIALES.id,
      }),
      requisito({
        id: "req-3",
        text: "Duración de 40 horas",
        kind: "condicion",
        status: "cumple",
        capability_question_id: null,
      }),
    ],
    paused_requirement_id: null,
    requires_technical_document: false,
    technical_document_reason: null,
    technical_document_ambiguous: null,
    warnings: [],
    discrepancy_decisions: [],
    content: null,
    last_instructions: null,
    created_by_user_id: "u-1",
    created_at: "2026-10-01T12:00:00Z",
    updated_at: "2026-10-01T12:00:00Z",
    is_expired: false,
    questions: [SEC, VIALES],
    catalog_items: [],
    changed_requirement_ids: [],
    // Borrador anterior a guardar con qué se analizó: no recomienda nada.
    analysis_documents: null,
    mentions_attachments: null,
    ...overrides,
  };
}
