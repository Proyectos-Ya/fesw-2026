/* eslint-disable react-hooks/set-state-in-effect -- bootstrap fetch pattern */

import { useCallback, useEffect, useState } from "react";

import type { TenderChatMessage } from "../types";
import {
  getTenderChatHistory,
  askTenderAssistant,
} from "../services/tenderAssistantService";

export function useTenderChat(tenderId: string) {
  const [messages, setMessages] = useState<TenderChatMessage[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState<boolean>(true);
  const [isAsking, setIsAsking] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const loadHistory = useCallback(async () => {
    if (!tenderId) {
      setMessages([]);
      setIsLoadingHistory(false);
      return;
    }
    setIsLoadingHistory(true);
    setError(null);
    try {
      const data = await getTenderChatHistory(tenderId);
      setMessages(data);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Error al cargar el historial";
      setError(msg);
    } finally {
      setIsLoadingHistory(false);
    }
  }, [tenderId]);

  const sendMessage = async (question: string): Promise<TenderChatMessage> => {
    const trimmed = question.trim();
    if (!trimmed) {
      throw new Error("La consulta no puede estar vacía.");
    }
    if (trimmed.length > 1000) {
      throw new Error("La consulta no puede exceder los 1000 caracteres.");
    }

    setIsAsking(true);
    setError(null);

    // Optimistic user message
    const tempUserMsg: TenderChatMessage = {
      id: `temp-${Date.now()}`,
      tender_id: tenderId,
      user_id: "current-user",
      role: "user",
      content: trimmed,
      citations: [],
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      const assistantMsg = await askTenderAssistant(tenderId, trimmed);
      setMessages((prev) => [...prev, assistantMsg]);
      return assistantMsg;
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Error al consultar el asistente";
      setError(msg);
      throw err;
    } finally {
      setIsAsking(false);
    }
  };

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  return {
    messages,
    isLoadingHistory,
    isAsking,
    error,
    loadHistory,
    sendMessage,
  };
}
