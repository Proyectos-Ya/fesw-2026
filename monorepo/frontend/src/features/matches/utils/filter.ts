import type { MatchingResult, Tender } from "../tenderTypes";

export interface BudgetRange {
  min: number | null;
  max: number | null;
}

export const EMPTY_BUDGET_RANGE: BudgetRange = { min: null, max: null };

export function isBudgetFilterActive(range: BudgetRange): boolean {
  return range.min !== null || range.max !== null;
}

/** Inclusive on both bounds. Tenders with unknown amount are rejected while the filter is active. */
export function tenderMatchesBudget(tender: Tender, range: BudgetRange): boolean {
  if (!isBudgetFilterActive(range)) return true;
  const amount = tender.available_amount_clp;
  if (amount == null) return false;
  if (range.min !== null && amount < range.min) return false;
  if (range.max !== null && amount > range.max) return false;
  return true;
}

export function filterMatchesByBudget(
  matches: MatchingResult[],
  range: BudgetRange,
): MatchingResult[] {
  if (!isBudgetFilterActive(range)) return matches;
  return matches.filter((m) => m.tender != null && tenderMatchesBudget(m.tender, range));
}

/** Tenders without region (or without tender) are rejected while the filter is active. */
export function filterMatchesByRegion(
  matches: MatchingResult[],
  region: string | null,
): MatchingResult[] {
  if (region === null) return matches;
  const wanted = region.trim().toLowerCase();
  return matches.filter(
    (m) => m.tender?.region != null && m.tender.region.trim().toLowerCase() === wanted,
  );
}

/** Unique regions present in the matches, alphabetically sorted (case-insensitive dedupe). */
export function listRegions(matches: MatchingResult[]): string[] {
  const seen = new Map<string, string>();
  for (const m of matches) {
    const region = m.tender?.region?.trim();
    if (!region) continue;
    const key = region.toLowerCase();
    if (!seen.has(key)) seen.set(key, region);
  }
  return [...seen.values()].sort((a, b) => a.localeCompare(b, "es"));
}
