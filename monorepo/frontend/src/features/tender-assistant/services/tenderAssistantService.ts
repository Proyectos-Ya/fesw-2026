import { apiFetch } from "@/features/shared/api/client";
import type { TenderChatDocument, TenderChatMessage, TenderChatSession } from "../types";

/**
 * Crea un nuevo hilo / sesión de conversación limpia para la licitación.
 */
export function createTenderChatSession(
  tenderId: string,
  title?: string,
): Promise<TenderChatSession> {
  return apiFetch<TenderChatSession>(`/tenders/${tenderId}/assistant/sessions`, {
    method: "POST",
    body: JSON.stringify({ title }),
  });
}

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
 * Envía una consulta en lenguaje natural al asistente virtual de la licitación en una sesión dada.
 */
export function askTenderAssistant(
  tenderId: string,
  question: string,
  sessionId?: string | null,
): Promise<TenderChatMessage> {
  return apiFetch<TenderChatMessage>(`/tenders/${tenderId}/assistant/ask`, {
    method: "POST",
    body: JSON.stringify({
      question,
      session_id: sessionId ?? null,
    }),
  });
}

/**
 * Obtiene el historial de mensajes de la licitación para la sesión activa o especificada.
 */
export function getTenderChatHistory(
  tenderId: string,
  sessionId?: string | null,
  limit: number = 50,
): Promise<TenderChatMessage[]> {
  const params = new URLSearchParams({ limit: limit.toString() });
  if (sessionId) {
    params.set("session_id", sessionId);
  }
  return apiFetch<TenderChatMessage[]>(
    `/tenders/${tenderId}/assistant/history?${params.toString()}`,
  );
}

