import { afterEach, describe, expect, it, vi } from "vitest";
import { apiFetch, ApiError } from "../client";

function mockFetchOnce(response: Response) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("apiFetch", () => {
  it("parsea el JSON de una respuesta exitosa", async () => {
    mockFetchOnce(
      new Response(JSON.stringify({ id: "u-1" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(apiFetch<{ id: string }>("/auth/me")).resolves.toEqual({ id: "u-1" });
  });

  it("resuelve sin parsear cuerpo en respuestas 204 (ej: logout)", async () => {
    mockFetchOnce(new Response(null, { status: 204 }));
    await expect(apiFetch<void>("/auth/logout", { method: "POST" })).resolves.toBeUndefined();
  });

  it("lanza ApiError con el detail del backend en errores HTTP", async () => {
    mockFetchOnce(
      new Response(JSON.stringify({ detail: "No autorizado" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(apiFetch("/auth/me")).rejects.toThrowError(
      expect.objectContaining({ name: "ApiError", status: 401, message: "No autorizado" }),
    );
    await expect(apiFetch("/auth/me")).rejects.toBeInstanceOf(ApiError);
  });
});
