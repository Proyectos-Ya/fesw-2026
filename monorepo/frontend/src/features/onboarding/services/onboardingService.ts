import { apiFetch } from "@/features/shared/api/client";
import type { UserPublic } from "@/features/auth/authSchema";

export async function markOnboardingCompletedApi(): Promise<UserPublic> {
  return apiFetch<UserPublic>("/users/me/onboarding", {
    method: "PATCH",
  });
}
