/**
 * Tipos de la postulación a una Compra Ágil (HU-20). Reflejan la API del backend
 * (`/tenders/{id}/proposal`); ver `docs/plans/230-generar-documentacion-postulacion.md`.
 */

export type ProposalStatus = "FEASIBILITY" | "PAUSED" | "STOPPED" | "READY";

export type RequirementKind =
  | "certificacion"
  | "experiencia"
  | "disponibilidad"
  | "condicion"
  | "documento"
  | "otro";

export type RequirementStatus = "cumple" | "no_cumple" | "parcial" | "desconocido";

export type Polarity = "afirmativa" | "negativa" | "neutra";

export type DecisionAction = "continue" | "stop";

export interface Requirement {
  id: string;
  text: string;
  kind: RequirementKind;
  mandatory: boolean;
  origin: string;
  status: RequirementStatus;
  catalog_item_id: string | null;
  capability_question_id: string | null;
  /** Sugerida para fortalecer la oferta: no la piden las bases. */
  suggested: boolean;
}

export interface DiscrepancyDecision {
  requirement_id: string;
  capability_question_id: string | null;
  action: DecisionAction;
  user_id: string;
  decided_at: string;
}

export interface ProposalWarning {
  requirement_id: string;
  text: string;
}

export interface DraftSource {
  id: string;
  label: string;
}

export interface DraftParagraph {
  text: string;
  sources: DraftSource[];
  placeholders: string[];
}

export interface DraftSection {
  paragraphs: DraftParagraph[];
}

export interface TechnicalSection {
  key: string;
  title: string;
  paragraphs: DraftParagraph[];
}

export interface TechnicalDocument {
  sections: TechnicalSection[];
}

export interface DraftContent {
  offer_name: DraftSection;
  offer_description: DraftSection;
  required_documents: DraftSection;
  technical_document: TechnicalDocument | null;
  /** Cuándo se redactó; `null` en los borradores anteriores a este dato. */
  generated_at?: string | null;
}

export interface CapabilityOption {
  label: string;
  polarity: Polarity;
}

export interface CapabilityQuestion {
  id: string;
  question: string;
  target_field: string;
  category: string;
  kind: "capacidad" | "certificacion" | "experiencia_proyecto";
  work_type: string | null;
  options: CapabilityOption[];
}

export interface ExperienceItem {
  id: string;
  origin: "perfil" | "capacidad" | "evidencia";
  kind: string;
  title: string;
  detail: string;
  polarity: Polarity | null;
  answered_by_user_id: string | null;
  tender_id: string | null;
  answered_at: string | null;
}

export interface ProposalDraft {
  id: string;
  supplier_id: string;
  tender_id: string;
  status: ProposalStatus;
  requirements: Requirement[];
  paused_requirement_id: string | null;
  requires_technical_document: boolean;
  technical_document_reason: string | null;
  warnings: ProposalWarning[];
  discrepancy_decisions: DiscrepancyDecision[];
  content: DraftContent | null;
  last_instructions: string | null;
  created_by_user_id: string | null;
  created_at: string;
  updated_at: string;
}

/** Lo que devuelve `GET /tenders/{id}/proposal`. */
export interface ProposalView extends ProposalDraft {
  is_expired: boolean;
  questions: CapabilityQuestion[];
  catalog_items: ExperienceItem[];
  /** Exigencias cuya respuesta en el banco cambió desde que se usó. */
  changed_requirement_ids: string[];
}

/** Etapa en curso, para el indicador del CA6. */
export type ProposalStage = "analyzing" | "drafting" | null;

/** Las que no se preguntan: definen la oferta, no a la empresa. */
export const KINDS_SIN_PREGUNTA: readonly RequirementKind[] = ["condicion", "documento"];
