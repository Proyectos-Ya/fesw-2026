import { apiFetch } from "@/features/shared/api/client";
import type { TenderDigest } from "../types";

export async function getTenderDigest(tenderId: string): Promise<TenderDigest> {
  return apiFetch<TenderDigest>(`/tenders/${encodeURIComponent(tenderId)}/digest`);
}
