import { afterEach, describe, expect, it, vi } from "vitest";
import { buildInteractionBody, reportTenderInteraction } from "../rankingTelemetryService";

const RK = "0b6f3d2e-8f1a-4c53-9a6e-2d1c7b9e4a10";

afterEach(() => {
  vi.unstubAllGlobals();
});

function stubFetch(response: { ok: boolean; status?: number; json?: () => Promise<unknown> }) {
  const fetchMock = vi.fn().mockResolvedValue({
    status: 202,
    json: async () => ({ recorded: true, attributed: true }),
    ...response,
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("reportTenderInteraction", () => {
  it("hace POST a /tenders/{id}/interactions con el ranking y la posición", async () => {
    const fetchMock = stubFetch({ ok: true });

    reportTenderInteraction("t-1", "detalle", "detalle", { rankingId: RK, position: 2 });

    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/tenders/t-1/interactions");
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body as string)).toEqual({
      kind: "detalle",
      source: "detalle",
      ranking_id: RK,
      position: 2,
    });
    expect(options.keepalive).toBe(true);
  });

  it("sin ranking no viaja la posición", async () => {
    const fetchMock = stubFetch({ ok: true });

    reportTenderInteraction("t-1", "ficha_mp", "detalle", null);

    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(options.body as string) as Record<string, unknown>;
    expect(body).toEqual({ kind: "ficha_mp", source: "detalle" });
    expect("position" in body).toBe(false);
  });

  it("un fetch rechazado no lanza ni deja rechazos sin manejar", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error("sin red"));
    vi.stubGlobal("fetch", fetchMock);

    expect(() => reportTenderInteraction("t-1", "detalle", "matches", null)).not.toThrow();
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    // Un tick más para que corra el catch de la promesa.
    await Promise.resolve();
  });

  it("una respuesta 500 no lanza", async () => {
    const fetchMock = stubFetch({
      ok: false,
      status: 500,
      json: async () => ({ detail: "boom" }),
    });

    expect(() => reportTenderInteraction("t-1", "guardar", "inicio", null)).not.toThrow();
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    await Promise.resolve();
  });
});

describe("buildInteractionBody", () => {
  it("incluye la posición solo si hay ranking", () => {
    expect(buildInteractionBody("impresion", "matches", { rankingId: RK, position: 4 })).toEqual({
      kind: "impresion",
      source: "matches",
      ranking_id: RK,
      position: 4,
    });
    expect(buildInteractionBody("impresion", "matches", null)).toEqual({
      kind: "impresion",
      source: "matches",
    });
  });
});
