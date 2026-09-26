import { apiFetch } from "@/features/shared/api/client";

import type {
  CalendarAuthorizationRequest,
  CalendarAuthorizationResult,
  CalendarConnection,
  CalendarProvider,
  MilestoneSyncResponse,
} from "../types";

export function getCalendarConnections(): Promise<CalendarConnection[]> {
  return apiFetch<CalendarConnection[]>("/calendar/connections");
}

export function startCalendarAuthorization(
  provider: CalendarProvider,
  request: CalendarAuthorizationRequest,
): Promise<{ authorization_url: string }> {
  return apiFetch<{ authorization_url: string }>(`/calendar/${provider}/authorize`, {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export function completeCalendarAuthorization(
  provider: CalendarProvider,
  code: string,
  state: string,
): Promise<CalendarAuthorizationResult> {
  return apiFetch<CalendarAuthorizationResult>(`/calendar/${provider}/callback`, {
    method: "POST",
    body: JSON.stringify({ code, state }),
  });
}

export function disconnectCalendar(provider: CalendarProvider): Promise<void> {
  return apiFetch<void>(`/calendar/connections/${provider}`, { method: "DELETE" });
}

export function syncMilestones(
  tenderId: string,
  provider: CalendarProvider,
  milestoneIds: string[],
  defaultTime: string | null,
): Promise<MilestoneSyncResponse> {
  return apiFetch<MilestoneSyncResponse>(
    `/tenders/${encodeURIComponent(tenderId)}/milestones/sync`,
    {
      method: "POST",
      body: JSON.stringify({ provider, milestone_ids: milestoneIds, default_time: defaultTime }),
    },
  );
}
