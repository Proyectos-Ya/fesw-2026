import { apiFetch } from "@/features/shared/api/client";

import type { CreatedShareLink, ShareLink, SharedTender } from "../types";

function linksPath(tenderId: string): string {
  return `/tenders/${encodeURIComponent(tenderId)}/share-links`;
}

export function createShareLink(tenderId: string): Promise<CreatedShareLink> {
  return apiFetch<CreatedShareLink>(linksPath(tenderId), { method: "POST" });
}

export function listShareLinks(tenderId: string): Promise<ShareLink[]> {
  return apiFetch<ShareLink[]>(linksPath(tenderId));
}

export function revokeShareLink(tenderId: string, linkId: string): Promise<void> {
  return apiFetch<void>(`${linksPath(tenderId)}/${encodeURIComponent(linkId)}`, {
    method: "DELETE",
  });
}

/** Público: no necesita sesión (criterio 2). */
export function getSharedTender(token: string): Promise<SharedTender> {
  return apiFetch<SharedTender>(`/shared/${encodeURIComponent(token)}`);
}
