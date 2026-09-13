/* eslint-disable react-hooks/set-state-in-effect -- bootstrap fetch pattern */

import { useCallback, useEffect, useState } from "react";

import type { TenderChatDocument } from "../types";
import { MAX_ATTACHED_DOCUMENTS } from "../types";
import {
  listTenderDocuments,
  uploadTenderDocument,
  deleteTenderDocument,
} from "../services/tenderAssistantService";
import { formatTenderAssistantError } from "../services/tenderErrorUtils";

export function useTenderDocuments(tenderId: string) {
  const [documents, setDocuments] = useState<TenderChatDocument[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const canUpload = documents.length < MAX_ATTACHED_DOCUMENTS;

  const loadDocuments = useCallback(async () => {
    if (!tenderId) {
      setDocuments([]);
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const data = await listTenderDocuments(tenderId);
      setDocuments(data);
    } catch (err) {
      const msg = formatTenderAssistantError(
        err,
        "No se pudieron cargar los documentos adjuntos de la licitación.",
      );
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [tenderId]);

  const uploadDocument = async (file: File): Promise<TenderChatDocument> => {
    if (documents.length >= MAX_ATTACHED_DOCUMENTS) {
      const limitMsg = `Se ha alcanzado el límite máximo de ${MAX_ATTACHED_DOCUMENTS} documentos adjuntos por chat.`;
      setError(limitMsg);
      throw new Error(limitMsg);
    }

    setIsUploading(true);
    setError(null);
    try {
      const newDoc = await uploadTenderDocument(tenderId, file);
      setDocuments((prev) => [...prev, newDoc]);
      return newDoc;
    } catch (err) {
      const msg = formatTenderAssistantError(
        err,
        "Error al subir documento. Verifica el formato y tamaño.",
      );
      setError(msg);
      throw new Error(msg);
    } finally {
      setIsUploading(false);
    }
  };

  const removeDocument = async (documentId: string): Promise<void> => {
    setError(null);
    try {
      await deleteTenderDocument(tenderId, documentId);
      setDocuments((prev) => prev.filter((d) => d.id !== documentId));
    } catch (err) {
      const msg = formatTenderAssistantError(err, "Error al eliminar documento.");
      setError(msg);
      throw new Error(msg);
    }
  };

  const clearError = () => {
    setError(null);
  };

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  return {
    documents,
    isLoading,
    isUploading,
    error,
    canUpload,
    maxDocuments: MAX_ATTACHED_DOCUMENTS,
    clearError,
    loadDocuments,
    uploadDocument,
    removeDocument,
  };
}
