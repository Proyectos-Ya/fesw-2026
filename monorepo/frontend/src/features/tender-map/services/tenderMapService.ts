import { apiFetch } from "@/features/shared/api/client";
import type { TenderMapResult } from "../types";

/** Marcadores de las licitaciones abiertas de `region` (nombre canónico o del perfil). */
export async function getTendersMap(region: string): Promise<TenderMapResult> {
  const params = new URLSearchParams({ region });
  return apiFetch<TenderMapResult>(`/tenders/map?${params.toString()}`);
}
