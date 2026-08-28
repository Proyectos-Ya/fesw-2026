import { afterEach, describe, expect, it, vi } from "vitest";
import {
  createTenderChatSession,
  uploadTenderDocument,
  listTenderDocuments,
  deleteTenderDocument,
  askTenderAssistant,
  getTenderChatHistory,
} from "../tenderAssistantService";
import type { TenderChatDocument, TenderChatMessage, TenderChatSession } from "../../types";

afterEach(() => {
  vi.unstubAllGlobals();
});

const mockSession: TenderChatSession = {
  id: "session-456",
  tender_id: "tender-abc",
  user_id: "user-xyz",
  title: "Nuevo Hilo",
  is_active: true,
  created_at: "2026-06-11T12:00:00Z",
  updated_at: "2026-06-11T12:00:00Z",
};

const mockDoc: TenderChatDocument = {
  id: "doc-123",
  tender_id: "tender-abc",
  file_name: "bases.pdf",
  file_type: "pdf",
  file_size_bytes: 1024,
  created_at: "2026-06-11T12:00:00Z",
};

const mockMsg: TenderChatMessage = {
  id: "msg-123",
  session_id: "session-456",
  tender_id: "tender-abc",
  user_id: "user-xyz",
  role: "assistant",
  content: "El plazo es de 3 días.",
  citations: [
    {
      document_name: "bases.pdf",
      page_or_sheet: "Pág 2",
      quote: "plazo de 3 días",
    },
  ],
  created_at: "2026-06-11T12:00:00Z",
};

describe("tenderAssistantService", () => {
  describe("createTenderChatSession", () => {
    it("hace POST a /tenders/:tenderId/assistant/sessions con el título opcional", async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        status: 201,
        json: async () => mockSession,
      });
      vi.stubGlobal("fetch", fetchMock);

      const result = await createTenderChatSession("tender-abc", "Nuevo Hilo");

      expect(fetchMock).toHaveBeenCalledOnce();
      const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
      expect(url).toContain("/tenders/tender-abc/assistant/sessions");
      expect(options.method).toBe("POST");
      expect(JSON.parse(options.body as string)).toEqual({
        title: "Nuevo Hilo",
      });
      expect(result).toEqual(mockSession);
    });
  });

  describe("uploadTenderDocument", () => {
    it("envía archivo vía FormData a /tenders/:tenderId/assistant/documents", async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        status: 201,
        json: async () => mockDoc,
      });
      vi.stubGlobal("fetch", fetchMock);

      const file = new File(["dummy content"], "bases.pdf", { type: "application/pdf" });
      const result = await uploadTenderDocument("tender-abc", file);

      expect(fetchMock).toHaveBeenCalledOnce();
      const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
      expect(url).toContain("/tenders/tender-abc/assistant/documents");
      expect(options.method).toBe("POST");
      expect(options.body).toBeInstanceOf(FormData);
      expect(result).toEqual(mockDoc);
    });
  });

  describe("listTenderDocuments", () => {
    it("hace GET a /tenders/:tenderId/assistant/documents", async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => [mockDoc],
      });
      vi.stubGlobal("fetch", fetchMock);

      const result = await listTenderDocuments("tender-abc");

      expect(fetchMock).toHaveBeenCalledOnce();
      const [url] = fetchMock.mock.calls[0] as [string];
      expect(url).toContain("/tenders/tender-abc/assistant/documents");
      expect(result).toEqual([mockDoc]);
    });
  });

  describe("deleteTenderDocument", () => {
    it("hace DELETE a /tenders/:tenderId/assistant/documents/:documentId", async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        status: 204,
      });
      vi.stubGlobal("fetch", fetchMock);

      await deleteTenderDocument("tender-abc", "doc-123");

      expect(fetchMock).toHaveBeenCalledOnce();
      const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
      expect(url).toContain("/tenders/tender-abc/assistant/documents/doc-123");
      expect(options.method).toBe("DELETE");
    });
  });

  describe("askTenderAssistant", () => {
    it("hace POST a /tenders/:tenderId/assistant/ask con pregunta y session_id", async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => mockMsg,
      });
      vi.stubGlobal("fetch", fetchMock);

      const result = await askTenderAssistant("tender-abc", "¿Cuál es el plazo?", "session-456");

      expect(fetchMock).toHaveBeenCalledOnce();
      const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
      expect(url).toContain("/tenders/tender-abc/assistant/ask");
      expect(options.method).toBe("POST");
      expect(JSON.parse(options.body as string)).toEqual({
        question: "¿Cuál es el plazo?",
        session_id: "session-456",
      });
      expect(result).toEqual(mockMsg);
    });
  });

  describe("getTenderChatHistory", () => {
    it("hace GET a /tenders/:tenderId/assistant/history con parámetros opcionales", async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => [mockMsg],
      });
      vi.stubGlobal("fetch", fetchMock);

      const result = await getTenderChatHistory("tender-abc", "session-456", 20);

      expect(fetchMock).toHaveBeenCalledOnce();
      const [url] = fetchMock.mock.calls[0] as [string];
      expect(url).toContain("/tenders/tender-abc/assistant/history?limit=20&session_id=session-456");
      expect(result).toEqual([mockMsg]);
    });
  });
});

