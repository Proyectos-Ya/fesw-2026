import { afterEach, describe, expect, it, vi } from "vitest";
import { getRecommendedTenders, generateDeepAnalysis, getDeepAnalysis } from "../tenderService";
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

    const result = await generateDeepAnalysis("tender-abc", "Priorizar ISO 9001", true);

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/tenders/tender-abc/analysis");
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body as string)).toEqual({
      prompt_instruction: "Priorizar ISO 9001",
      force_regenerate: true,
    });
    expect(result).toEqual(mockAnalysis);
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
    });
    expect(result).toEqual(mockAnalysis);
  });
});
