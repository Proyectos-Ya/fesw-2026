import { apiFetch } from "@/features/shared/api/client";
import type { DynamicQuestionDTO, Question } from "../questionTypes";

export function getSmartQuestions(tenderId?: string): Promise<Question[]> {
  const endpoint = tenderId
    ? `/questions?tender_id=${encodeURIComponent(tenderId)}`
    : "/questions";
  return apiFetch<Question[]>(endpoint);
}

export interface AnswerQuestionInput {
  question_id: string;
  answer: "Sí" | "No" | string;
  target_profile_field?: string | null;
  supplier_id?: string;
}

export function answerSmartQuestion(payload: AnswerQuestionInput): Promise<{ status: string; detail: string }> {
  return apiFetch<{ status: string; detail: string }>("/questions/answer", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
