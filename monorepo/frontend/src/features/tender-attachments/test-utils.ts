import type { OfficialAttachment, TenderAttachments } from "./types";

export function buildOfficialAttachment(
  overrides: Partial<OfficialAttachment> = {},
): OfficialAttachment {
  return {
    id: "a-1",
    mp_document_id: 1931002,
    name: "Anexo 3 Composición personalidad juridica.xlsx",
    ext: "xlsx",
    status: "missing",
    ...overrides,
  };
}

export function buildTenderAttachments(
  overrides: Partial<TenderAttachments> = {},
): TenderAttachments {
  return {
    official: [buildOfficialAttachment()],
    list_synced_at: "2026-09-28T16:28:00Z",
    ...overrides,
  };
}
