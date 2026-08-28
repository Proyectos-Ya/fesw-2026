import { afterEach, describe, expect, it, vi } from "vitest";
import {
  uploadTenderDocument,
  listTenderDocuments,
  deleteTenderDocument,
  askTenderAssistant,
  getTenderChatHistory,
} from "../tenderAssistantService";
import type { TenderChatDocument, TenderChatMessage } from "../../types";

afterEach(() => {
  vi.unstubAllGlobals();
});

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
    it("hace POST a /tenders/:tenderId/assistant/ask con la pregunta", async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => mockMsg,
      });
      vi.stubGlobal("fetch", fetchMock);

      const result = await askTenderAssistant("tender-abc", "¿Cuál es el plazo?");

      expect(fetchMock).toHaveBeenCalledOnce();
      const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
      expect(url).toContain("/tenders/tender-abc/assistant/ask");
      expect(options.method).toBe("POST");
      expect(JSON.parse(options.body as string)).toEqual({
        question: "¿Cuál es el plazo?",
      });
      expect(result).toEqual(mockMsg);
    });
  });

  describe("getTenderChatHistory", () => {
    it("hace GET a /tenders/:tenderId/assistant/history", async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => [mockMsg],
      });
      vi.stubGlobal("fetch", fetchMock);

      const result = await getTenderChatHistory("tender-abc");

      expect(fetchMock).toHaveBeenCalledOnce();
      const [url] = fetchMock.mock.calls[0] as [string];
      expect(url).toContain("/tenders/tender-abc/assistant/history");
      expect(result).toEqual([mockMsg]);
    });
  });
});
