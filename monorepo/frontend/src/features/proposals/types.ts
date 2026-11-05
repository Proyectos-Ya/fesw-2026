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
  /** Qué poner en esta sección; es fija. `null` en los borradores antiguos. */
  guidance?: string | null;
  /** Sugerencia de la IA para esta licitación. `null` en los borradores antiguos. */
  hint?: string | null;
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

/**
 * Un proyecto que respalda un "Sí" a una pregunta `experiencia_proyecto`
 * (`POST /capabilities/questions/{id}/evidence`). El catálogo lo trae después
 * como `evidencia:<id>` y la redacción lo puede citar.
 */
export interface CapabilityEvidenceInput {
  title: string;
  year: number;
  buyer?: string | null;
  amount_clp?: number | null;
  description?: string | null;
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
  /**
   * Las bases mencionan un informe o documento técnico sin aclarar si va con la
   * cotización. `null` en los borradores anteriores a este dato.
   */
  technical_document_ambiguous: boolean | null;
  warnings: ProposalWarning[];
  discrepancy_decisions: DiscrepancyDecision[];
  content: DraftContent | null;
  last_instructions: string | null;
  created_by_user_id: string | null;
  created_at: string;
  updated_at: string;
}

/** Un adjunto que el análisis recibió. `corrupted`: no se pudo leer. */
export interface AnalysisDocument {
  name: string;
  corrupted: boolean;
}

/** Lo que devuelve `GET /tenders/{id}/proposal`. */
export interface ProposalView extends ProposalDraft {
  is_expired: boolean;
  questions: CapabilityQuestion[];
  catalog_items: ExperienceItem[];
  /** Exigencias cuya respuesta en el banco cambió desde que se usó. */
  changed_requirement_ids: string[];
  /**
   * Con qué adjuntos se hizo el análisis. `null` en los borradores anteriores a
   * este dato: ahí no se sabe y no se recomienda nada sobre las bases.
   */
  analysis_documents: AnalysisDocument[] | null;
  /** Si la ficha menciona bases, TDR o anexos. `null` igual que arriba. */
  mentions_attachments: boolean | null;
}

/** Etapa en curso, para el indicador del CA6. */
export type ProposalStage = "analyzing" | "drafting" | "regenerating" | null;

/** La opción que el usuario acaba de pulsar, mientras se guarda. */
export interface PendingAnswer {
  questionId: string;
  label: string;
}

/** Las que no se preguntan: definen la oferta, no a la empresa. */
export const KINDS_SIN_PREGUNTA: readonly RequirementKind[] = ["condicion", "documento"];

// --- Postulación en Mercado Público (HU-032) ---

export interface PostulationTenderInfo {
  id: string;
  code: string;
  title?: string;
  name?: string;
  closing_at?: string | null;
  url?: string;
}

export interface PostulationCompanyInfo {
  rut: string;
  name?: string;
  legal_name?: string;
  trade_name?: string | null;
  contact_name?: string | null;
  contact_email?: string | null;
  contact_phone?: string | null;
}

export interface PostulationItem {
  line_number?: number;
  position?: number;
  product_code?: string | null;
  name: string;
  description?: string | null;
  quantity: number;
  unit?: string;
  unit_of_measure?: string | null;
  suggested_unit_price?: number;
  unit_price?: number | null;
  suggested_total_price?: number;
  price_source?: string;
  quotation_quantity?: number | null;
  technical_spec?: string | null;
}

export interface PostulationRequiredDocument {
  id?: string;
  name: string;
  type?: string;
  description?: string | null;
  matched_file_name?: string | null;
  status?: "attached" | "placeholder" | "missing" | string;
  download_url?: string | null;
  is_mandatory?: boolean;
  kind?: string;
}

export interface PostulationPackage {
  tender: PostulationTenderInfo;
  company: PostulationCompanyInfo;
  items: PostulationItem[];
  total_suggested_clp?: number;
  observations?: string;
  offer_name?: string;
  offer_description?: string;
  offer_description_placeholders?: string[];
  validity_days?: number;
  delivery_term_days?: number;
  technical_document_available?: boolean;
  required_documents?: PostulationRequiredDocument[];
  warnings?: string[];
  quotation_updated_at?: string | null;
  shipping_clp?: number | null;
}

