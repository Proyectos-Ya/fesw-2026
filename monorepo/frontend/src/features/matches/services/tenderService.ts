import { apiFetch } from "@/features/shared/api/client";
import type { MatchingResult, DeepAnalysis } from "../tenderTypes";
import { ApiError } from "@/features/shared/api/client";

interface GetRecommendedOptions {
  forceRefresh?: boolean;
}

/**
 * Backend route: GET /tenders/recomended (sic — typo lives in the backend router).
 * Returns matches sorted by final_score desc.
 */
export function getRecommendedTenders(
  userId: string,
  options: GetRecommendedOptions = {},
): Promise<MatchingResult[]> {
  const params = new URLSearchParams({ profile_id: userId });
  if (options.forceRefresh) params.set("force_refresh", "true");
  return apiFetch<MatchingResult[]>(`/tenders/recomended?${params.toString()}`);
}

/**
 * Backend route: POST /tenders/{tender_id}/analysis
 * Genera u obtiene el análisis profundo de compatibilidad IA.
 */
export function generateDeepAnalysis(
  tenderId: string,
  promptInstruction?: string,
  forceRegenerate?: boolean,
  onlyIfExists?: boolean,
): Promise<DeepAnalysis> {
  return apiFetch<DeepAnalysis>(`/tenders/${tenderId}/analysis`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      prompt_instruction: promptInstruction || null,
      force_regenerate: forceRegenerate || false,
      only_if_exists: onlyIfExists || false,
    }),
  });
}

/**
 * Obtiene el análisis de compatibilidad IA actual solo si ya existe (sin forzar la generación inicial).
 */
export async function getDeepAnalysisOnly(tenderId: string): Promise<DeepAnalysis | null> {
  try {
    return await generateDeepAnalysis(tenderId, undefined, false, true);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      return null;
    }
    throw err;
  }
}

/**
 * Obtiene el análisis de compatibilidad IA actual sin forzar la regeneración.
 */
export function getDeepAnalysis(tenderId: string): Promise<DeepAnalysis> {
  return generateDeepAnalysis(tenderId, undefined, false);
}
