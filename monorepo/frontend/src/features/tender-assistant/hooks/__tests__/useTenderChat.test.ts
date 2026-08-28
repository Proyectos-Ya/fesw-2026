import { renderHook, waitFor, act } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { useTenderChat } from "../useTenderChat";
import * as tenderAssistantService from "../../services/tenderAssistantService";
import type { TenderChatMessage } from "../../types";

vi.mock("../../services/tenderAssistantService");

const mockUserMsg: TenderChatMessage = {
  id: "msg-1",
  tender_id: "tender-1",
  user_id: "user-1",
  role: "user",
  content: "¿Cuál es el presupuesto?",
  citations: [],
  created_at: "2026-06-11T12:00:00Z",
};

const mockAssistantMsg: TenderChatMessage = {
  id: "msg-2",
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
  it("carga el historial inicial de la licitación", async () => {
    vi.mocked(tenderAssistantService.getTenderChatHistory).mockResolvedValue([mockUserMsg, mockAssistantMsg]);

    const { result } = renderHook(() => useTenderChat("tender-1"));

    expect(result.current.isLoadingHistory).toBe(true);
    await waitFor(() => expect(result.current.isLoadingHistory).toBe(false));

    expect(result.current.messages).toHaveLength(2);
    expect(result.current.error).toBeNull();
  });

  it("permite enviar una pregunta, agrega el mensaje del usuario y del asistente", async () => {
    vi.mocked(tenderAssistantService.getTenderChatHistory).mockResolvedValue([]);
    vi.mocked(tenderAssistantService.askTenderAssistant).mockResolvedValue(mockAssistantMsg);

    const { result } = renderHook(() => useTenderChat("tender-1"));
    await waitFor(() => expect(result.current.isLoadingHistory).toBe(false));

    await act(async () => {
      await result.current.sendMessage("¿Cuál es el presupuesto?");
    });

    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[0].role).toBe("user");
    expect(result.current.messages[0].content).toBe("¿Cuál es el presupuesto?");
    expect(result.current.messages[1].role).toBe("assistant");
    expect(result.current.messages[1].content).toBe("El presupuesto es de $10.000.000.");
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
