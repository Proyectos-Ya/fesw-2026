import { describe, expect, it } from "vitest";

import { buildAttachmentFile } from "../../test-utils";
import { SHARING_NOTICES, sharingNotice } from "../sharing";

describe("sharingNotice", () => {
  it("devuelve null cuando no hay archivo", () => {
    expect(sharingNotice(null)).toBeNull();
  });

  it("devuelve null en un archivo ajeno aunque esté en conflicto", () => {
    const file = buildAttachmentFile({ is_mine: false, status: "stored", trust: "conflict" });
    expect(sharingNotice(file)).toBeNull();
  });

  it("devuelve aviso de conflicto en un archivo propio guardado", () => {
    const file = buildAttachmentFile({ is_mine: true, status: "stored", trust: "conflict" });
    expect(sharingNotice(file)).toBe(SHARING_NOTICES.conflict);
  });

  it("devuelve aviso de rechazo en un archivo propio guardado", () => {
    const file = buildAttachmentFile({ is_mine: true, status: "stored", trust: "rejected" });
    expect(sharingNotice(file)).toBe(SHARING_NOTICES.rejected);
  });

  it("devuelve null si el archivo falló en la subida (status rejected) aunque trust sea rejected", () => {
    const file = buildAttachmentFile({ is_mine: true, status: "rejected", trust: "rejected" });
    expect(sharingNotice(file)).toBeNull();
  });

  it("devuelve null cuando trust es pending o corroborated", () => {
    expect(
      sharingNotice(buildAttachmentFile({ is_mine: true, status: "stored", trust: "pending" })),
    ).toBeNull();
    expect(
      sharingNotice(buildAttachmentFile({ is_mine: true, status: "stored", trust: "corroborated" })),
    ).toBeNull();
  });
});
