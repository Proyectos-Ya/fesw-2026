import { apiFetch } from "@/features/shared/api/client";
import type { LoginData, RegisterData, UserPublic } from "../authSchema";

export async function login(data: LoginData): Promise<{ access_token: string }> {
  return apiFetch<{ access_token: string }>("/auth/login", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function register(data: RegisterData): Promise<UserPublic> {
  return apiFetch<UserPublic>("/auth/register", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function logout(): Promise<void> {
  return apiFetch<void>("/auth/logout", {
    method: "POST",
  });
}

export async function getMe(): Promise<UserPublic> {
  return apiFetch<UserPublic>("/auth/me");
}
