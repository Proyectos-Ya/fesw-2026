import { apiFetch } from "@/features/shared/api/client";

import type { TenderAttachments } from "../types";

/** Lista oficial de anexos de la licitación, tal como la publica Mercado Público. */
export function getTenderAttachments(tenderId: string): Promise<TenderAttachments> {
  return apiFetch<TenderAttachments>(`/tenders/${encodeURIComponent(tenderId)}/attachments`);
}
