import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiFetch } from "@/features/shared/api/client";
import { buildTenderAttachments } from "../../test-utils";
import { getTenderAttachments } from "../tenderAttachmentsService";

vi.mock("@/features/shared/api/client", () => ({
  apiFetch: vi.fn(),
}));

describe("tenderAttachmentsService", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
    vi.mocked(apiFetch).mockResolvedValue(buildTenderAttachments());
  });

  it("consulta los anexos oficiales de la licitación", async () => {
    await expect(getTenderAttachments("t-1")).resolves.toEqual(buildTenderAttachments());

    expect(apiFetch).toHaveBeenCalledWith("/tenders/t-1/attachments");
  });

  it("codifica el id en la ruta", async () => {
    await getTenderAttachments("a/b");

    expect(apiFetch).toHaveBeenCalledWith("/tenders/a%2Fb/attachments");
  });
});
