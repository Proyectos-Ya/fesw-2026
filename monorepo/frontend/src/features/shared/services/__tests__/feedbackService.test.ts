import { describe, it, expect, vi } from "vitest";
import * as client from "@/features/shared/api/client";
import { submitAppComment, submitAppReview } from "../feedbackService";

describe("feedbackService (HU-24)", () => {
  it("envía comentario o queja a POST /feedback/comments (S6)", async () => {
    const fetchSpy = vi.spyOn(client, "apiFetch").mockResolvedValueOnce({
      id: "f-1",
      user_id: "u-1",
      kind: "comment",
      message: "Falta integración con Excel",
      anonymous: false,
      created_at: "2026-10-27T10:00:00Z",
    });

    const res = await submitAppComment("Falta integración con Excel");
    expect(res.id).toBe("f-1");
    expect(fetchSpy).toHaveBeenCalledWith("/feedback/comments", {
      method: "POST",
      body: JSON.stringify({ message: "Falta integración con Excel" }),
    });
  });

  it("envía reseña con estrellas, comentario y anonimato a POST /feedback/reviews (S7)", async () => {
    const fetchSpy = vi.spyOn(client, "apiFetch").mockResolvedValueOnce({
      id: "f-2",
      user_id: "u-1",
      kind: "review",
      rating: 5,
      message: "Muy buena herramienta",
      anonymous: true,
      created_at: "2026-10-27T10:00:00Z",
    });

    const res = await submitAppReview({ rating: 5, message: "Muy buena herramienta", anonymous: true });
    expect(res.rating).toBe(5);
    expect(fetchSpy).toHaveBeenCalledWith("/feedback/reviews", {
      method: "POST",
      body: JSON.stringify({ rating: 5, message: "Muy buena herramienta", anonymous: true }),
    });
  });
});
