import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiFetch } from "@/features/shared/api/client";
import {
  completeCalendarAuthorization,
  disconnectCalendar,
  getCalendarConnections,
  startCalendarAuthorization,
  syncMilestones,
} from "../calendarService";

vi.mock("@/features/shared/api/client", () => ({
  apiFetch: vi.fn(),
}));

describe("calendarService", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
    vi.mocked(apiFetch).mockResolvedValue(undefined);
  });

  it("consulta las conexiones", async () => {
    await getCalendarConnections();

    expect(apiFetch).toHaveBeenCalledWith("/calendar/connections");
  });

  it("inicia la autorización con los hitos y la hora por defecto", async () => {
    await startCalendarAuthorization("google", {
      tender_id: "t-1",
      milestone_ids: ["m-1", "m-2"],
      default_time: "09:00",
    });

    expect(apiFetch).toHaveBeenCalledWith("/calendar/google/authorize", {
      method: "POST",
      body: JSON.stringify({ tender_id: "t-1", milestone_ids: ["m-1", "m-2"], default_time: "09:00" }),
    });
  });

  it("completa la autorización con el código y el state", async () => {
    await completeCalendarAuthorization("google", "codigo", "estado");

    expect(apiFetch).toHaveBeenCalledWith("/calendar/google/callback", {
      method: "POST",
      body: JSON.stringify({ code: "codigo", state: "estado" }),
    });
  });

  it("sincroniza los hitos elegidos con la hora por defecto", async () => {
    await syncMilestones("t-1", "google", ["m-1"], "09:00");

    expect(apiFetch).toHaveBeenCalledWith("/tenders/t-1/milestones/sync", {
      method: "POST",
      body: JSON.stringify({ provider: "google", milestone_ids: ["m-1"], default_time: "09:00" }),
    });
  });

  it("desconecta con DELETE", async () => {
    await disconnectCalendar("google");

    expect(apiFetch).toHaveBeenCalledWith("/calendar/connections/google", { method: "DELETE" });
  });
});
