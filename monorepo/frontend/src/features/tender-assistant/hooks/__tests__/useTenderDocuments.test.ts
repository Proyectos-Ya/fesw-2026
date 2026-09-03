import { renderHook, waitFor, act } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { useTenderDocuments } from "../useTenderDocuments";
import * as tenderAssistantService from "../../services/tenderAssistantService";
import type { TenderChatDocument } from "../../types";
import { MAX_ATTACHED_DOCUMENTS } from "../../types";

vi.mock("../../services/tenderAssistantService");

const mockDoc: TenderChatDocument = {
  id: "doc-1",
  tender_id: "tender-1",
  file_name: "bases.pdf",
  file_type: "pdf",
  file_size_bytes: 2048,
  created_at: "2026-06-11T12:00:00Z",
};

const createMockDocs = (count: number): TenderChatDocument[] =>
  Array.from({ length: count }, (_, i) => ({
    id: `doc-${i + 1}`,
    tender_id: "tender-1",
    file_name: `doc_${i + 1}.pdf`,
    file_type: "pdf" as const,
    file_size_bytes: 1024 * (i + 1),
    created_at: "2026-06-11T12:00:00Z",
  }));

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
    expect(result.current.canUpload).toBe(true);
    expect(result.current.maxDocuments).toBe(10);
  });

  it("permite subir un documento y lo agrega a la lista", async () => {
    vi.mocked(tenderAssistantService.listTenderDocuments).mockResolvedValue([]);
    vi.mocked(tenderAssistantService.uploadTenderDocument).mockResolvedValue(mockDoc);

    const { result } = renderHook(() => useTenderDocuments("tender-1"));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    const file = new File(["pdf content"], "bases.pdf", { type: "application/pdf" });

    await act(async () => {
      await result.current.uploadDocument(file);
    });

    expect(result.current.documents).toEqual([mockDoc]);
    expect(result.current.isUploading).toBe(false);
  });

  it("rechaza la subida si ya se alcanzó el límite de 10 documentos (CA5)", async () => {
    const tenDocs = createMockDocs(MAX_ATTACHED_DOCUMENTS);
    vi.mocked(tenderAssistantService.listTenderDocuments).mockResolvedValue(tenDocs);

    const { result } = renderHook(() => useTenderDocuments("tender-1"));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.documents).toHaveLength(10);
    expect(result.current.canUpload).toBe(false);

    const extraFile = new File(["extra content"], "extra.pdf", { type: "application/pdf" });

    await act(async () => {
      await expect(result.current.uploadDocument(extraFile)).rejects.toThrow(
        "Se ha alcanzado el límite máximo de 10 documentos adjuntos por chat."
      );
    });

    expect(result.current.error).toBe(
      "Se ha alcanzado el límite máximo de 10 documentos adjuntos por chat."
    );
    expect(tenderAssistantService.uploadTenderDocument).not.toHaveBeenCalled();
  });

  it("captura y expone mensaje de error cuando un archivo está dañado o corrupto (CA6)", async () => {
    vi.mocked(tenderAssistantService.listTenderDocuments).mockResolvedValue([]);
    const corruptedErrorMsg =
      "El archivo 'corrupto.pdf' no posee una cabecera PDF válida o está dañado.";
    vi.mocked(tenderAssistantService.uploadTenderDocument).mockRejectedValue(
      new Error(corruptedErrorMsg)
    );

    const { result } = renderHook(() => useTenderDocuments("tender-1"));
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    const corruptedFile = new File(["not a pdf"], "corrupto.pdf", {
      type: "application/pdf",
    });

    await act(async () => {
      await expect(result.current.uploadDocument(corruptedFile)).rejects.toThrow(
        corruptedErrorMsg
      );
    });

    expect(result.current.error).toBe(corruptedErrorMsg);
    expect(result.current.isUploading).toBe(false);
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
    expect(result.current.canUpload).toBe(true);
  });
});
