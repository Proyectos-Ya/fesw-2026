import { apiFetch } from "@/features/shared/api/client";
import type { UserPublic } from "@/features/auth/authSchema";

export type TourName = "home" | "detail" | "draft";

export async function markOnboardingCompletedApi(
  tourName: TourName,
): Promise<UserPublic> {
  return apiFetch<UserPublic>("/users/me/onboarding", {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ tour_name: tourName }),
  });
}
