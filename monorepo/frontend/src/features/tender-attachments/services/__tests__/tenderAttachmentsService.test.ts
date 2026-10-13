import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiFetch } from "@/features/shared/api/client";
import { buildAttachmentFile, buildTenderAttachments, buildUploadTicket } from "../../test-utils";
import {
  completeUpload,
  deleteAttachmentFile,
  getTenderAttachments,
  requestUploadUrl,
} from "../tenderAttachmentsService";

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

describe("subida de anexos", () => {
  const body = {
    file_name: "Bases.pdf",
    size_bytes: 4,
    mime: "application/pdf",
    sha256: "b221d9dbb083a7f33428d7c2a3c3198ae925614d70210e28716ccaa7cd4ddb79",
  };

  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("pide la URL de subida con el cuerpo en JSON", async () => {
    vi.mocked(apiFetch).mockResolvedValue(buildUploadTicket());

    await expect(requestUploadUrl("t-1", "a-1", body)).resolves.toEqual(buildUploadTicket());

    expect(apiFetch).toHaveBeenCalledWith("/tenders/t-1/attachments/a-1/upload-url", {
      method: "POST",
      body: JSON.stringify(body),
    });
  });

  it("confirma la subida con POST y sin cuerpo", async () => {
    vi.mocked(apiFetch).mockResolvedValue(buildAttachmentFile());

    await expect(completeUpload("t-1", "u-1")).resolves.toEqual(buildAttachmentFile());

    expect(apiFetch).toHaveBeenCalledWith("/tenders/t-1/attachments/uploads/u-1/complete", {
      method: "POST",
    });
  });

  it("borra el archivo con DELETE", async () => {
    vi.mocked(apiFetch).mockResolvedValue(undefined);

    await deleteAttachmentFile("t-1", "f-1");

    expect(apiFetch).toHaveBeenCalledWith("/tenders/t-1/attachments/files/f-1", {
      method: "DELETE",
    });
  });

  it("codifica todos los ids en la ruta", async () => {
    vi.mocked(apiFetch).mockResolvedValue(undefined);

    await requestUploadUrl("a/b", "c/d", body);
    await completeUpload("a/b", "u/1");
    await deleteAttachmentFile("a/b", "f/1");

    expect(vi.mocked(apiFetch).mock.calls.map(([path]) => path)).toEqual([
      "/tenders/a%2Fb/attachments/c%2Fd/upload-url",
      "/tenders/a%2Fb/attachments/uploads/u%2F1/complete",
      "/tenders/a%2Fb/attachments/files/f%2F1",
    ]);
  });
});
