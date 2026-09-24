import type { MilestoneList, TenderMilestone } from "./types";

export function buildMilestone(overrides: Partial<TenderMilestone> = {}): TenderMilestone {
  return {
    id: "m-1",
    kind: "cierre_postulacion",
    title: "Cierre de recepción de ofertas",
    description: null,
    source: "mercado_publico",
    source_excerpt: null,
    due_at: "2026-10-20T18:00:00Z",
    has_time: true,
    urgency: "normal",
    synced_providers: [],
    ...overrides,
  };
}

export function buildMilestoneList(overrides: Partial<MilestoneList> = {}): MilestoneList {
  return {
    milestones: [buildMilestone()],
    documents_count: 0,
    discarded_count: 0,
    ...overrides,
  };
}
