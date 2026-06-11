import { apiFetch } from "@/features/shared/api/client";
import type { Question } from "../questionTypes";

export function getSmartQuestions(profileId: string): Promise<Question[]> {
  return apiFetch<Question[]>(`/questions?profileId=${encodeURIComponent(profileId)}`);
}
