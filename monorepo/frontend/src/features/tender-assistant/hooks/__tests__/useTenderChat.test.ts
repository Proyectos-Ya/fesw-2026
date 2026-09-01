import { renderHook, waitFor, act } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { useTenderChat, HISTORY_LOAD_ERROR_MESSAGE } from "../useTenderChat";
import * as tenderAssistantService from "../../services/tenderAssistantService";
import type { TenderChatMessage, TenderChatSession } from "../../types";

vi.mock("../../services/tenderAssistantService");

const mockSession: TenderChatSession = {
  id: "session-1",
  tender_id: "tender-1",
  user_id: "user-1",
  title: null,
  is_active: true,
  created_at: "2026-06-11T12:00:00Z",
  updated_at: "2026-06-11T12:00:00Z",
};

const mockUserMsg: TenderChatMessage = {
  id: "msg-1",
  session_id: "session-1",
  tender_id: "tender-1",
  user_id: "user-1",
  role: "user",
  content: "¿Cuál es el presupuesto?",
  citations: [],
  created_at: "2026-06-11T12:00:00Z",
};

const mockAssistantMsg: TenderChatMessage = {
  id: "msg-2",
  session_id: "session-1",
  tender_id: "tender-1",
  user_id: "user-1",
  role: "assistant",
  content: "El presupuesto es de $10.000.000.",
  citations: [
    {
      document_name: "bases.pdf",
      page_or_sheet: "Pág 3",
      quote: "$10.000.000 IVA incluido",
    },
  ],
  created_at: "2026-06-11T12:00:05Z",
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useTenderChat", () => {
  it("carga el historial inicial de la licitación y extrae el sessionId", async () => {
    vi.mocked(tenderAssistantService.getTenderChatHistory).mockResolvedValue([mockUserMsg, mockAssistantMsg]);

    const { result } = renderHook(() => useTenderChat("tender-1"));

    expect(result.current.isLoadingHistory).toBe(true);
    await waitFor(() => expect(result.current.isLoadingHistory).toBe(false));

    expect(result.current.messages).toHaveLength(2);
    expect(result.current.sessionId).toBe("session-1");
    expect(result.current.error).toBeNull();
    expect(result.current.historyError).toBeNull();
  });

  it("establece historyError cuando falla la carga del historial desde el backend", async () => {
    vi.mocked(tenderAssistantService.getTenderChatHistory).mockRejectedValue(new Error("500 Internal Server Error"));

    const { result } = renderHook(() => useTenderChat("tender-1"));

    await waitFor(() => expect(result.current.isLoadingHistory).toBe(false));

    expect(result.current.historyError).toBe(HISTORY_LOAD_ERROR_MESSAGE);
    expect(result.current.messages).toHaveLength(0);
  });

  it("permite enviar una pregunta con sessionId y agrega las respuestas", async () => {
    vi.mocked(tenderAssistantService.getTenderChatHistory).mockResolvedValue([mockUserMsg]);
    vi.mocked(tenderAssistantService.askTenderAssistant).mockResolvedValue(mockAssistantMsg);

    const { result } = renderHook(() => useTenderChat("tender-1"));
    await waitFor(() => expect(result.current.isLoadingHistory).toBe(false));

    await act(async () => {
      await result.current.sendMessage("¿Y cuál es el plazo?");
    });

    expect(tenderAssistantService.askTenderAssistant).toHaveBeenCalledWith("tender-1", "¿Y cuál es el plazo?", "session-1");
    expect(result.current.messages).toHaveLength(3);
  });

  it("startNewChat crea una nueva sesión y limpia los mensajes de la memoria", async () => {
    vi.mocked(tenderAssistantService.getTenderChatHistory).mockResolvedValue([mockUserMsg, mockAssistantMsg]);
    vi.mocked(tenderAssistantService.createTenderChatSession).mockResolvedValue({
      ...mockSession,
      id: "session-2",
    });

    const { result } = renderHook(() => useTenderChat("tender-1"));
    await waitFor(() => expect(result.current.isLoadingHistory).toBe(false));
    expect(result.current.messages).toHaveLength(2);

    await act(async () => {
      await result.current.startNewChat();
    });

    expect(tenderAssistantService.createTenderChatSession).toHaveBeenCalledWith("tender-1", undefined);
    expect(result.current.sessionId).toBe("session-2");
    expect(result.current.messages).toHaveLength(0);
    expect(result.current.historyError).toBeNull();
  });

  it("retryHistory reintenta cargar el historial", async () => {
    vi.mocked(tenderAssistantService.getTenderChatHistory)
      .mockRejectedValueOnce(new Error("Network Error"))
      .mockResolvedValueOnce([mockUserMsg]);

    const { result } = renderHook(() => useTenderChat("tender-1"));
    await waitFor(() => expect(result.current.isLoadingHistory).toBe(false));
    expect(result.current.historyError).toBe(HISTORY_LOAD_ERROR_MESSAGE);

    await act(async () => {
      await result.current.retryHistory();
    });

    expect(result.current.historyError).toBeNull();
    expect(result.current.messages).toHaveLength(1);
  });

  it("captura errores al enviar y actualiza el estado de error", async () => {
    vi.mocked(tenderAssistantService.getTenderChatHistory).mockResolvedValue([]);
    vi.mocked(tenderAssistantService.askTenderAssistant).mockRejectedValue(
      new Error("El asistente virtual se encuentra temporalmente fuera de servicio"),
    );

    const { result } = renderHook(() => useTenderChat("tender-1"));
    await waitFor(() => expect(result.current.isLoadingHistory).toBe(false));

    await act(async () => {
      try {
        await result.current.sendMessage("Pregunta");
      } catch {
        // expected
      }
    });

    expect(result.current.error).toContain("El asistente virtual se encuentra temporalmente fuera de servicio");
    expect(result.current.isAsking).toBe(false);
  });
});

