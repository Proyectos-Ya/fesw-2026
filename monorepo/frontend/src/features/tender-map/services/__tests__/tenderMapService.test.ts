import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/features/shared/api/client";
import { buildTenderMapResult } from "../../test-utils";
import { getTendersMap } from "../tenderMapService";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("getTendersMap", () => {
  it("pide GET /tenders/map con la región codificada", async () => {
    const resultado = buildTenderMapResult({ region: "Metropolitana de Santiago" });
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => resultado });
    vi.stubGlobal("fetch", fetchMock);

    const respuesta = await getTendersMap("Metropolitana de Santiago");

    const [url] = fetchMock.mock.calls[0] as [string];
    const parsed = new URL(url, "http://localhost");
    expect(parsed.pathname).toBe("/api/tenders/map");
    expect(parsed.searchParams.get("region")).toBe("Metropolitana de Santiago");
    expect(respuesta).toEqual(resultado);
  });

  it("propaga el error de la API para que la vista ofrezca reintentar", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        json: async () => ({ detail: "No se pudo cargar el mapa." }),
      }),
    );

    await expect(getTendersMap("Los Lagos")).rejects.toBeInstanceOf(ApiError);
  });
});
