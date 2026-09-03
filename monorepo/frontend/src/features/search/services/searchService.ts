import { apiFetch } from "@/features/shared/api/client";
import type { TenderSearchParams, TenderSearchResult } from "../types";

/**
 * Realiza una búsqueda de licitaciones en el backend (GET /tenders/search).
 * Soporta búsqueda semántica por texto y filtros estructurados (regiones, montos, fechas, estados).
 */
export function searchTenders(
  params: TenderSearchParams = {},
): Promise<TenderSearchResult> {
  const searchParams = new URLSearchParams();

  if (params.q && params.q.trim()) {
    searchParams.set("q", params.q.trim());
  }

  if (params.regions) {
    for (const region of params.regions) {
      if (region.trim()) {
        searchParams.append("regions", region.trim());
      }
    }
  }

  if (params.province_id !== undefined && params.province_id !== null) {
    searchParams.set("province_id", String(params.province_id));
  }

  if (params.commune_id !== undefined && params.commune_id !== null) {
    searchParams.set("commune_id", String(params.commune_id));
  }

  if (params.status_codes) {
    for (const status of params.status_codes) {
      if (status.trim()) {
        searchParams.append("status_codes", status.trim());
      }
    }
  }

  if (params.closing_from) {
    searchParams.set("closing_from", params.closing_from);
  }

  if (params.closing_to) {
    searchParams.set("closing_to", params.closing_to);
  }

  if (params.published_from) {
    searchParams.set("published_from", params.published_from);
  }

  if (params.published_to) {
    searchParams.set("published_to", params.published_to);
  }

  if (params.min_amount !== undefined && params.min_amount !== null) {
    searchParams.set("min_amount", String(params.min_amount));
  }

  if (params.max_amount !== undefined && params.max_amount !== null) {
    searchParams.set("max_amount", String(params.max_amount));
  }

  if (params.limit !== undefined && params.limit !== null) {
    searchParams.set("limit", String(params.limit));
  }

  if (params.offset !== undefined && params.offset !== null) {
    searchParams.set("offset", String(params.offset));
  }

  const query = searchParams.toString();
  const path = query ? `/tenders/search?${query}` : "/tenders/search";

  return apiFetch<TenderSearchResult>(path);
}
