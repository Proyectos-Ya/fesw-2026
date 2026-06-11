import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getRecommendedTenders,
  generateDeepAnalysis,
  getDeepAnalysisOnly,
  getDeepAnalysis,
} from "../tenderService";
import { ApiError } from "@/features/shared/api/client";
import type { DeepAnalysis } from "../../tenderTypes";

const mockAnalysis: DeepAnalysis = {
  id: "da-123",
  tender_id: "tender-abc",
  supplier_id: "supplier-xyz",
  compatibility_score: 85.0,
  recommendation: "Postular",
  justification: "Excelente compatibilidad.",
  prompt_instruction: "instruccion de prueba",
  created_at: "2026-06-11T12:00:00Z",
  updated_at: "2026-06-11T12:00:00Z",
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("getRecommendedTenders", () => {
  it("hace GET a /tenders/recomended con profile_id", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    });
    vi.stubGlobal("fetch", fetchMock);

    await getRecommendedTenders("supplier-xyz");

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain("/tenders/recomended?profile_id=supplier-xyz");
  });
});

describe("generateDeepAnalysis", () => {
  it("hace POST a /tenders/id/analysis con el prompt e instrucciones opcionales", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockAnalysis,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await generateDeepAnalysis("tender-abc", "Priorizar ISO 9001", true, false);

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/tenders/tender-abc/analysis");
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body as string)).toEqual({
      prompt_instruction: "Priorizar ISO 9001",
      force_regenerate: true,
      only_if_exists: false,
    });
    expect(result).toEqual(mockAnalysis);
  });
});

describe("getDeepAnalysisOnly", () => {
  it("hace POST pidiendo only_if_exists: true y devuelve el analisis si existe (200)", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockAnalysis,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await getDeepAnalysisOnly("tender-abc");

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/tenders/tender-abc/analysis");
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body as string)).toEqual({
      prompt_instruction: null,
      force_regenerate: false,
      only_if_exists: true,
    });
    expect(result).toEqual(mockAnalysis);
  });

  it("devuelve null si el servidor responde con error 404 (no existe analisis generado)", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: "Not Found",
      json: async () => ({ detail: "El analisis no ha sido generado" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await getDeepAnalysisOnly("tender-abc");

    expect(fetchMock).toHaveBeenCalledOnce();
    expect(result).toBeNull();
  });

  it("lanza ApiError si el servidor responde con otro codigo de error (ej: 500)", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      json: async () => ({ detail: "Internal error" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(getDeepAnalysisOnly("tender-abc")).rejects.toBeInstanceOf(ApiError);
  });
});

describe("getDeepAnalysis", () => {
  it("hace POST a /tenders/id/analysis con force_regenerate en false y sin prompt", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockAnalysis,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await getDeepAnalysis("tender-abc");

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/tenders/tender-abc/analysis");
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body as string)).toEqual({
      prompt_instruction: null,
      force_regenerate: false,
      only_if_exists: false,
    });
    expect(result).toEqual(mockAnalysis);
  });
});
