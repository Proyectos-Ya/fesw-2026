import type { Tender } from "@/features/matches/tenderTypes";

export interface TenderSearchParams {
  q?: string;
  regions?: string[];
  status_codes?: string[];
  closing_from?: string;
  closing_to?: string;
  published_from?: string;
  published_to?: string;
  min_amount?: number;
  max_amount?: number;
  limit?: number;
  offset?: number;
}

export interface TenderSearchResult {
  items: Tender[];
  total: number;
  is_truncated?: boolean;
}
