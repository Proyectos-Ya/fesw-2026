import { renderHook, waitFor, act } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { useTenderDocuments } from "../useTenderDocuments";
import * as tenderAssistantService from "../../services/tenderAssistantService";
import type { TenderChatDocument } from "../../types";

vi.mock("../../services/tenderAssistantService");

const mockDoc: TenderChatDocument = {
  id: "doc-1",
  tender_id: "tender-1",
  file_name: "bases.pdf",
  file_type: "pdf",
  file_size_bytes: 2048,
  created_at: "2026-06-11T12:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useTenderDocuments (HU-05.2)", () => {
  it("carga documentos al inicializar", async () => {
    vi.mocked(tenderAssistantService.listTenderDocuments).mockResolvedValue([mockDoc]);

    const { result } = renderHook(() => useTenderDocuments("tender-1"));

    expect(result.current.isLoading).toBe(true);
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.documents).toEqual([mockDoc]);
    expect(result.current.error).toBeNull();
  });

  it("no permite subir: el asistente lee los anexos de la licitación", async () => {
    vi.mocked(tenderAssistantService.listTenderDocuments).mockResolvedValue([]);

    const { result } = renderHook(() => useTenderDocuments("tender-1"));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current).not.toHaveProperty("uploadDocument");
    expect(result.current).not.toHaveProperty("isUploading");
  });

  it("permite eliminar un documento y lo quita de la lista", async () => {
    vi.mocked(tenderAssistantService.listTenderDocuments).mockResolvedValue([mockDoc]);
    vi.mocked(tenderAssistantService.deleteTenderDocument).mockResolvedValue(undefined);

    const { result } = renderHook(() => useTenderDocuments("tender-1"));
    await waitFor(() => expect(result.current.documents).toHaveLength(1));

    await act(async () => {
      await result.current.removeDocument("doc-1");
    });

    expect(result.current.documents).toEqual([]);
  });
});
