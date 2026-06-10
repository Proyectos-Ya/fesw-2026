import { apiFetch } from "@/features/shared/api/client";
import type { MatchingResult } from "../tenderTypes";

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
