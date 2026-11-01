import { apiFetch } from "@/features/shared/api/client";

export interface AppFeedbackResponse {
  id: string;
  user_id: string;
  kind: "comment" | "review";
  message?: string | null;
  rating?: number | null;
  anonymous: boolean;
  created_at: string;
}

export interface SubmitReviewPayload {
  rating?: number | null;
  message?: string | null;
  anonymous?: boolean;
}

/**
 * Envía un mensaje, comentario y/o queja del sistema desde ajustes (HU-24, S6).
 */
export function submitAppComment(message: string): Promise<AppFeedbackResponse> {
  return apiFetch<AppFeedbackResponse>("/feedback/comments", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

/**
 * Envía una reseña (0-5 estrellas, comentario opcional, anónima o con nombre) (HU-24, S7).
 */
export function submitAppReview(payload: SubmitReviewPayload): Promise<AppFeedbackResponse> {
  return apiFetch<AppFeedbackResponse>("/feedback/reviews", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
