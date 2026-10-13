import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiFetch } from "@/features/shared/api/client";
import { buildTenderDigest } from "../../test-utils";
import { getTenderDigest } from "../tenderDigestService";

vi.mock("@/features/shared/api/client", () => ({
  apiFetch: vi.fn(),
}));

describe("tenderDigestService", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
    vi.mocked(apiFetch).mockResolvedValue(buildTenderDigest());
  });

  it("consulta el digest de la licitación", async () => {
    await expect(getTenderDigest("t-1")).resolves.toEqual(buildTenderDigest());

    expect(apiFetch).toHaveBeenCalledWith("/tenders/t-1/digest");
  });

  it("codifica el id en la ruta", async () => {
    await getTenderDigest("a/b");

    expect(apiFetch).toHaveBeenCalledWith("/tenders/a%2Fb/digest");
  });
});
