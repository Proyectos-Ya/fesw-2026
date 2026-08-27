import { apiFetch } from "@/features/shared/api/client";
import type { MatchingResult } from "@/features/matches/tenderTypes";

export async function fetchSavedTenders(): Promise<MatchingResult[]> {
  return apiFetch<MatchingResult[]>("/tenders/saved");
}

export async function saveTenderApi(tenderId: string): Promise<void> {
  return apiFetch<void>(`/tenders/${tenderId}/saved`, {
    method: "POST",
  });
}

export async function unsaveTenderApi(tenderId: string): Promise<void> {
  return apiFetch<void>(`/tenders/${tenderId}/saved`, {
    method: "DELETE",
  });
}