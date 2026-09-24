import { apiFetch } from "@/features/shared/api/client";

import type { MilestoneList } from "../types";

export function getTenderMilestones(tenderId: string): Promise<MilestoneList> {
  return apiFetch<MilestoneList>(`/tenders/${encodeURIComponent(tenderId)}/milestones`);
}

export function extractTenderMilestones(tenderId: string): Promise<MilestoneList> {
  return apiFetch<MilestoneList>(`/tenders/${encodeURIComponent(tenderId)}/milestones/extract`, {
    method: "POST",
  });
}
