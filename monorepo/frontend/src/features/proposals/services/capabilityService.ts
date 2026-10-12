import { apiFetch } from "@/features/shared/api/client";
import type { CapabilityEvidenceInput } from "../types";

/**
 * Agrega un proyecto que respalda un "Sí" a una pregunta de experiencia en
 * proyectos. 409 si la empresa no respondió "Sí" a esa pregunta; 422 si los
 * datos no son válidos (por ejemplo, un año fuera de rango).
 */
export function addCapabilityEvidence(
  questionId: string,
  data: CapabilityEvidenceInput,
): Promise<unknown> {
  return apiFetch<unknown>(`/capabilities/questions/${questionId}/evidence`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}
