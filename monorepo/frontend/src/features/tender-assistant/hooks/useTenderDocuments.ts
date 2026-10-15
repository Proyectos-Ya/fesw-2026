/* eslint-disable react-hooks/set-state-in-effect -- bootstrap fetch pattern */

import { useCallback, useEffect, useState } from "react";

import type { TenderChatDocument } from "../types";
import {
  listTenderDocuments,
  deleteTenderDocument,
} from "../services/tenderAssistantService";
import { formatTenderAssistantError } from "../services/tenderErrorUtils";

/**
 * Documentos que quedaron en el chat antes de retirar la subida. El asistente lee
 * los anexos de la licitación; acá solo se listan y se pueden borrar.
 */
export function useTenderDocuments(tenderId: string) {
  const [documents, setDocuments] = useState<TenderChatDocument[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

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
    error,
    clearError,
    loadDocuments,
    removeDocument,
  };
}
