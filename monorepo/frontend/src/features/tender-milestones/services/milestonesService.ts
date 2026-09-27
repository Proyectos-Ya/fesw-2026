import { apiFetch } from "@/features/shared/api/client";

import type { MilestoneList, MilestoneReminderResponse, ReminderDaysBefore } from "../types";

export function getTenderMilestones(tenderId: string): Promise<MilestoneList> {
  return apiFetch<MilestoneList>(`/tenders/${encodeURIComponent(tenderId)}/milestones`);
}

export function extractTenderMilestones(tenderId: string): Promise<MilestoneList> {
  return apiFetch<MilestoneList>(`/tenders/${encodeURIComponent(tenderId)}/milestones/extract`, {
    method: "POST",
  });
}

/** Activa el recordatorio del hito, o lo apaga con `null`. */
export function setMilestoneReminder(
  tenderId: string,
  milestoneId: string,
  daysBefore: ReminderDaysBefore | null,
): Promise<MilestoneReminderResponse> {
  return apiFetch<MilestoneReminderResponse>(
    `/tenders/${encodeURIComponent(tenderId)}/milestones/${encodeURIComponent(milestoneId)}/reminder`,
    { method: "PATCH", body: JSON.stringify({ days_before: daysBefore }) },
  );
}
