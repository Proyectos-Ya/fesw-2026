/* eslint-disable react-hooks/set-state-in-effect -- bootstrap fetch pattern */

import { useCallback, useEffect, useState } from "react";

import type { TenderChatMessage } from "../types";
import {
  getTenderChatHistory,
  askTenderAssistant,
  createTenderChatSession,
} from "../services/tenderAssistantService";

export const HISTORY_LOAD_ERROR_MESSAGE =
  "No se pudo cargar el historial de la conversación. Por favor reintente más tarde o inicie un nuevo chat.";

export function useTenderChat(tenderId: string) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<TenderChatMessage[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState<boolean>(true);
  const [isAsking, setIsAsking] = useState<boolean>(false);
  const [isStartingNewChat, setIsStartingNewChat] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);

  const loadHistory = useCallback(
    async (targetSessionId?: string | null) => {
      if (!tenderId) {
        setMessages([]);
        setSessionId(null);
        setIsLoadingHistory(false);
        setHistoryError(null);
        return;
      }
      setIsLoadingHistory(true);
      setHistoryError(null);
      setError(null);
      try {
        const data = await getTenderChatHistory(tenderId, targetSessionId ?? undefined);
        setMessages(data);
        if (targetSessionId) {
          setSessionId(targetSessionId);
        } else if (data.length > 0 && data[0].session_id) {
          setSessionId(data[0].session_id);
        }
      } catch {
        setHistoryError(HISTORY_LOAD_ERROR_MESSAGE);
      } finally {
        setIsLoadingHistory(false);
      }
    },
    [tenderId],
  );

  const startNewChat = useCallback(
    async (title?: string) => {
      if (!tenderId) return null;
      setIsStartingNewChat(true);
      setError(null);
      setHistoryError(null);
      try {
        const newSession = await createTenderChatSession(tenderId, title);
        setSessionId(newSession.id);
        setMessages([]);
        return newSession;
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Error al iniciar un nuevo chat";
        setError(msg);
        throw err;
      } finally {
        setIsStartingNewChat(false);
      }
    },
    [tenderId],
  );

  const retryHistory = useCallback(() => {
    return loadHistory(sessionId);
  }, [loadHistory, sessionId]);

  const sendMessage = async (question: string): Promise<TenderChatMessage> => {
    if (historyError) {
      throw new Error("No se puede enviar consultas debido a un error de historial.");
    }
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
      session_id: sessionId,
      tender_id: tenderId,
      user_id: "current-user",
      role: "user",
      content: trimmed,
      citations: [],
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      const assistantMsg = await askTenderAssistant(tenderId, trimmed, sessionId);
      if (assistantMsg.session_id && !sessionId) {
        setSessionId(assistantMsg.session_id);
      }
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
    setSessionId(null);
    void loadHistory(null);
  }, [loadHistory]);

  return {
    sessionId,
    messages,
    isLoadingHistory,
    isAsking,
    isStartingNewChat,
    error,
    historyError,
    loadHistory,
    startNewChat,
    retryHistory,
    sendMessage,
  };
}

