import { apiDownload, apiFetch, type ArchivoDescargado } from "@/features/shared/api/client";
import type { DecisionAction, ProposalDraft, ProposalView } from "../types";

const base = (tenderId: string) => `/tenders/${tenderId}/proposal`;

/** Borrador de la empresa activa, con preguntas y origen de la cobertura. 404 si no hay. */
export function getProposal(tenderId: string): Promise<ProposalView> {
  return apiFetch<ProposalView>(base(tenderId));
}

/** Etapa 1 del CA6: "Analizando bases y experiencia". */
export function startFeasibility(tenderId: string): Promise<ProposalDraft> {
  return apiFetch<ProposalDraft>(`${base(tenderId)}/feasibility`, { method: "POST" });
}

/**
 * Repite la factibilidad, por ejemplo tras subir las bases. Si nada cambió
 * (adjuntos, perfil o ficha), el backend devuelve el mismo borrador.
 */
export function reanalyzeProposal(tenderId: string): Promise<ProposalDraft> {
  return apiFetch<ProposalDraft>(`${base(tenderId)}/reanalyze`, { method: "POST" });
}

export function answerProposalQuestion(
  tenderId: string,
  questionId: string,
  answer: string,
): Promise<ProposalDraft> {
  return apiFetch<ProposalDraft>(`${base(tenderId)}/questions/${questionId}/answer`, {
    method: "POST",
    body: JSON.stringify({ answer }),
  });
}

/** CA8 (`continue`) o CA9 (`stop`) sobre la exigencia que el usuario vio en el aviso. */
export function decideDiscrepancy(
  tenderId: string,
  requirementId: string,
  action: DecisionAction,
): Promise<ProposalDraft> {
  return apiFetch<ProposalDraft>(`${base(tenderId)}/discrepancy`, {
    method: "POST",
    body: JSON.stringify({ requirement_id: requirementId, action }),
  });
}

export function resumeProposal(tenderId: string): Promise<ProposalDraft> {
  return apiFetch<ProposalDraft>(`${base(tenderId)}/resume`, { method: "POST" });
}

/** Etapa 2 del CA6: "Redactando nombre, descripción y documentos". */
export function generateProposal(tenderId: string): Promise<ProposalDraft> {
  return apiFetch<ProposalDraft>(`${base(tenderId)}/generate`, { method: "POST" });
}

/** CA4: vuelve a redactar con instrucciones libres. */
export function regenerateProposal(
  tenderId: string,
  instructions: string,
): Promise<ProposalDraft> {
  return apiFetch<ProposalDraft>(`${base(tenderId)}/regenerate`, {
    method: "POST",
    body: JSON.stringify({ instructions }),
  });
}

/** CA3: solo el documento técnico, cuando las bases lo exigen. */
export function downloadTechnicalDocument(tenderId: string): Promise<ArchivoDescargado> {
  return apiDownload(`${base(tenderId)}/export.docx`, "documento-tecnico.docx");
}
