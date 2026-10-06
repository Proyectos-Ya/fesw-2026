import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiFetch } from "@/features/shared/api/client";
import {
  createShareLink,
  getSharedTender,
  listShareLinks,
  revokeShareLink,
} from "../sharingService";

vi.mock("@/features/shared/api/client", () => ({
  apiFetch: vi.fn(),
}));

describe("sharingService", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
    vi.mocked(apiFetch).mockResolvedValue(undefined);
  });

  it("crea el enlace con POST", async () => {
    await createShareLink("t-1");

    expect(apiFetch).toHaveBeenCalledWith("/tenders/t-1/share-links", { method: "POST" });
  });

  it("lista los enlaces vigentes", async () => {
    await listShareLinks("t-1");

    expect(apiFetch).toHaveBeenCalledWith("/tenders/t-1/share-links");
  });

  it("revoca con DELETE", async () => {
    await revokeShareLink("t-1", "l-1");

    expect(apiFetch).toHaveBeenCalledWith("/tenders/t-1/share-links/l-1", {
      method: "DELETE",
    });
  });

  it("abre el enlace público por su token", async () => {
    await getSharedTender("abc_DEF-123");

    expect(apiFetch).toHaveBeenCalledWith("/shared/abc_DEF-123");
  });

  it("codifica los segmentos de la ruta", async () => {
    await getSharedTender("a/b");
    await revokeShareLink("t/1", "l/1");

    expect(apiFetch).toHaveBeenCalledWith("/shared/a%2Fb");
    expect(apiFetch).toHaveBeenCalledWith("/tenders/t%2F1/share-links/l%2F1", {
      method: "DELETE",
    });
  });
});
