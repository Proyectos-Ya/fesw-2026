import { apiFetch } from "@/features/shared/api/client";
import type { TenderChatDocument, TenderChatMessage } from "../types";

/**
 * Carga un documento adjunto para el asistente de la licitación (.pdf, .xlsx, .png).
 */
export function uploadTenderDocument(
  tenderId: string,
  file: File,
): Promise<TenderChatDocument> {
  const formData = new FormData();
  formData.append("file", file);

  return apiFetch<TenderChatDocument>(`/tenders/${tenderId}/assistant/documents`, {
    method: "POST",
    body: formData,
  });
}

/**
 * Obtiene la lista de documentos adjuntos asociados al chat de la licitación.
 */
export function listTenderDocuments(tenderId: string): Promise<TenderChatDocument[]> {
  return apiFetch<TenderChatDocument[]>(`/tenders/${tenderId}/assistant/documents`);
}

/**
 * Elimina un documento adjunto por su ID.
 */
export function deleteTenderDocument(
  tenderId: string,
  documentId: string,
): Promise<void> {
  return apiFetch<void>(`/tenders/${tenderId}/assistant/documents/${documentId}`, {
    method: "DELETE",
  });
}

/**
 * Envía una consulta en lenguaje natural al asistente virtual de la licitación.
 */
export function askTenderAssistant(
  tenderId: string,
  question: string,
): Promise<TenderChatMessage> {
  return apiFetch<TenderChatMessage>(`/tenders/${tenderId}/assistant/ask`, {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}

/**
 * Obtiene el historial de mensajes de la licitación.
 */
export function getTenderChatHistory(
  tenderId: string,
  limit: number = 50,
): Promise<TenderChatMessage[]> {
  return apiFetch<TenderChatMessage[]>(
    `/tenders/${tenderId}/assistant/history?limit=${limit}`,
  );
}
