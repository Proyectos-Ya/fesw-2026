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

/** Tenders without province (or without tender) are rejected while the filter is active. */
export function filterMatchesByProvince(
  matches: MatchingResult[],
  province: string | null,
): MatchingResult[] {
  if (province === null) return matches;
  const wanted = province.trim().toLowerCase();
  return matches.filter(
    (m) => m.tender?.province != null && m.tender.province.trim().toLowerCase() === wanted,
  );
}

/** Unique provinces present in the matches, alphabetically sorted (case-insensitive dedupe). */
export function listProvinces(matches: MatchingResult[]): string[] {
  const seen = new Map<string, string>();
  for (const m of matches) {
    const province = m.tender?.province?.trim();
    if (!province) continue;
    const key = province.toLowerCase();
    if (!seen.has(key)) seen.set(key, province);
  }
  return [...seen.values()].sort((a, b) => a.localeCompare(b, "es"));
}
