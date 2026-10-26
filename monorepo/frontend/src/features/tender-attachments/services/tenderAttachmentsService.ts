import { apiFetch } from "@/features/shared/api/client";

import type {
  AttachmentFile,
  TenderAttachments,
  UploadUrlRequest,
  UploadUrlResponse,
} from "../types";

const enc = encodeURIComponent;

/** Lista oficial de anexos de la licitación y lo que la empresa activa subió para cada uno. */
export function getTenderAttachments(tenderId: string): Promise<TenderAttachments> {
  return apiFetch<TenderAttachments>(`/tenders/${enc(tenderId)}/attachments`);
}

/**
 * Primer paso de la subida: declara el archivo y recibe la URL firmada (201) o,
 * si la empresa ya tiene ese archivo para el anexo, el archivo existente (200).
 */
export function requestUploadUrl(
  tenderId: string,
  attachmentId: string,
  body: UploadUrlRequest,
): Promise<UploadUrlResponse> {
  return apiFetch<UploadUrlResponse>(
    `/tenders/${enc(tenderId)}/attachments/${enc(attachmentId)}/upload-url`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

/** Tercer paso: el backend verifica que el archivo llegó completo al almacenamiento. */
export function completeUpload(tenderId: string, uploadId: string): Promise<AttachmentFile> {
  return apiFetch<AttachmentFile>(
    `/tenders/${enc(tenderId)}/attachments/uploads/${enc(uploadId)}/complete`,
    { method: "POST" },
  );
}

/** Borra un archivo que subió la empresa activa. */
export function deleteAttachmentFile(tenderId: string, fileId: string): Promise<void> {
  return apiFetch<void>(`/tenders/${enc(tenderId)}/attachments/files/${enc(fileId)}`, {
    method: "DELETE",
  });
}
