import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiFetch } from "@/features/shared/api/client";
import { extractTenderMilestones, getTenderMilestones } from "../milestonesService";

vi.mock("@/features/shared/api/client", () => ({
  apiFetch: vi.fn(),
}));

const LISTA = { milestones: [], documents_count: 0, discarded_count: 0 };

describe("milestonesService", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
    vi.mocked(apiFetch).mockResolvedValue(LISTA);
  });

  it("consulta los hitos de la licitación", async () => {
    await expect(getTenderMilestones("t-1")).resolves.toEqual(LISTA);

    expect(apiFetch).toHaveBeenCalledWith("/tenders/t-1/milestones");
  });

  it("pide la extracción con POST", async () => {
    await extractTenderMilestones("t-1");

    expect(apiFetch).toHaveBeenCalledWith("/tenders/t-1/milestones/extract", {
      method: "POST",
    });
  });

  it("codifica el id en la ruta", async () => {
    await getTenderMilestones("a/b");

    expect(apiFetch).toHaveBeenCalledWith("/tenders/a%2Fb/milestones");
  });
});
