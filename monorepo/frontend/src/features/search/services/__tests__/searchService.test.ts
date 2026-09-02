import { afterEach, describe, expect, it, vi } from "vitest";
import { searchTenders } from "../searchService";
import type { TenderSearchResult } from "../../types";

const mockResult: TenderSearchResult = {
  items: [
    {
      id: "tender-123",
      code: "1234-56-COT26",
      name: "Adquisición de Insumos Médicos",
      description: "Descripción de prueba",
      status_id: 1,
      status_code: "publicada",
      published_at: "2026-06-01T10:00:00Z",
      closing_at: "2026-06-10T18:00:00Z",
      last_change_at: "2026-06-01T10:00:00Z",
      buyer_rut: "12345678-9",
      buyer_name: "Hospital Central",
      buyer_unit: "Abastecimiento",
      region: "Región Metropolitana de Santiago",
      province: "Santiago",
      commune: "Santiago",
      available_amount_clp: 5000000,
      created_at: "2026-06-01T10:00:00Z",
      updated_at: "2026-06-01T10:00:00Z",
      items: [],
    },
  ],
  total: 1,
  is_truncated: false,
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("searchTenders", () => {
  it("llama a GET /tenders/search sin query params cuando no se pasan filtros", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockResult,
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await searchTenders();

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toBe("http://localhost:8000/tenders/search");
    expect(result).toEqual(mockResult);
  });

  it("formatea correctamente los query params simples y de texto", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockResult,
    });
    vi.stubGlobal("fetch", fetchMock);

    await searchTenders({
      q: "computadores portátiles",
      min_amount: 100000,
      max_amount: 5000000,
      limit: 50,
      offset: 10,
      closing_from: "2026-06-01T00:00:00Z",
      closing_to: "2026-06-30T23:59:59Z",
      published_from: "2026-05-01T00:00:00Z",
      published_to: "2026-05-31T23:59:59Z",
    });

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url] = fetchMock.mock.calls[0] as [string];
    const parsedUrl = new URL(url);

    expect(parsedUrl.pathname).toBe("/tenders/search");
    expect(parsedUrl.searchParams.get("q")).toBe("computadores portátiles");
    expect(parsedUrl.searchParams.get("min_amount")).toBe("100000");
    expect(parsedUrl.searchParams.get("max_amount")).toBe("5000000");
    expect(parsedUrl.searchParams.get("limit")).toBe("50");
    expect(parsedUrl.searchParams.get("offset")).toBe("10");
    expect(parsedUrl.searchParams.get("closing_from")).toBe("2026-06-01T00:00:00Z");
    expect(parsedUrl.searchParams.get("closing_to")).toBe("2026-06-30T23:59:59Z");
    expect(parsedUrl.searchParams.get("published_from")).toBe("2026-05-01T00:00:00Z");
    expect(parsedUrl.searchParams.get("published_to")).toBe("2026-05-31T23:59:59Z");
  });

  it("agrega múltiples entradas para arrays como regions y status_codes", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockResult,
    });
    vi.stubGlobal("fetch", fetchMock);

    await searchTenders({
      regions: [
        "Región Metropolitana de Santiago",
        "Región de Valparaíso",
      ],
      status_codes: ["publicada", "adjudicada"],
    });

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url] = fetchMock.mock.calls[0] as [string];
    const parsedUrl = new URL(url);

    expect(parsedUrl.searchParams.getAll("regions")).toEqual([
      "Región Metropolitana de Santiago",
      "Región de Valparaíso",
    ]);
    expect(parsedUrl.searchParams.getAll("status_codes")).toEqual([
      "publicada",
      "adjudicada",
    ]);
  });

  it("formatea correctamente los query params province_id y commune_id como enteros", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockResult,
    });
    vi.stubGlobal("fetch", fetchMock);

    await searchTenders({
      province_id: 51,
      commune_id: 295,
    });

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url] = fetchMock.mock.calls[0] as [string];
    const parsedUrl = new URL(url);

    expect(parsedUrl.pathname).toBe("/tenders/search");
    expect(parsedUrl.searchParams.get("province_id")).toBe("51");
    expect(parsedUrl.searchParams.get("commune_id")).toBe("295");
  });
});
