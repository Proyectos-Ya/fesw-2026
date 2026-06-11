import { apiFetch } from "@/features/shared/api/client";
import type { Question } from "../questionTypes";

export function getSmartQuestions(profileId: string): Promise<Question[]> {
  return apiFetch<Question[]>(`/questions?profileId=${encodeURIComponent(profileId)}`);
}

export interface AnswerQuestionInput {
  supplier_id: string;
  question_id: string;
  target_profile_field: string;
  answer: string;
}

export function answerSmartQuestion(payload: AnswerQuestionInput): Promise<{ status: string; detail: string }> {
  return apiFetch<{ status: string; detail: string }>("/questions/answer", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}