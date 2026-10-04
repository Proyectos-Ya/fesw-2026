import type {
  AttachmentFile,
  OfficialAttachment,
  TenderAttachments,
  UploadTicket,
} from "./types";

export function buildOfficialAttachment(
  overrides: Partial<OfficialAttachment> = {},
): OfficialAttachment {
  return {
    id: "a-1",
    mp_document_id: 1931002,
    name: "Anexo 3 Composición personalidad juridica.xlsx",
    name_normalized: "anexo 3 composicion personalidad juridica.xlsx",
    ext: "xlsx",
    status: "missing",
    file: null,
    ...overrides,
  };
}

export function buildTenderAttachments(
  overrides: Partial<TenderAttachments> = {},
): TenderAttachments {
  return {
    official: [buildOfficialAttachment()],
    list_synced_at: "2026-09-28T16:28:00Z",
    quota: null,
    can_upload: false,
    max_upload_size_bytes: 52428800,
    ...overrides,
  };
}

export function buildAttachmentFile(overrides: Partial<AttachmentFile> = {}): AttachmentFile {
  return {
    id: "f-1",
    size_bytes: 2048,
    source: "manual",
    visibility: "private",
    trust: "pending",
    status: "stored",
    is_mine: true,
    created_at: "2026-10-03T15:00:00Z",
    ...overrides,
  };
}

export function buildUploadTicket(overrides: Partial<UploadTicket> = {}): UploadTicket {
  return {
    deduplicated: false,
    upload_id: "u-1",
    url: "https://almacen.test/put",
    method: "PUT",
    headers: {
      "x-amz-checksum-sha256": "siHZ27CDp/M0KNfCo8MZiuklYU1wIQ4ocWzKp81N23k=",
      "Content-Type": "application/pdf",
    },
    expires_at: "2026-10-03T15:15:00Z",
    ...overrides,
  };
}
