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

describe("apiFetch — origen de la API", () => {
  it("llama a una ruta relativa bajo /api, no al dominio del backend", async () => {
    // La cookie de sesión es httpOnly y la emite el backend. Si el navegador la
    // pide a otro dominio (Railway) es una cookie de tercera parte: SameSite=Lax
    // no la envía y los navegadores con bloqueo de terceros la descartan aunque
    // sea SameSite=None. El síntoma en producción fue login 200 seguido de
    // /auth/me 401 en bucle. Con una ruta relativa el navegador habla solo con
    // el dominio del frontend y el rewrite de Next reenvía al backend por
    // detrás, así que la cookie vuelve a ser de primera parte.
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch<void>("/auth/logout", { method: "POST" });

    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toBe("/api/auth/logout");
    expect(url).not.toMatch(/^https?:\/\//);
  });

  it("envía las credenciales para que la cookie de sesión viaje", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch<void>("/auth/logout", { method: "POST" });

    expect(fetchMock.mock.calls[0][1]).toMatchObject({ credentials: "include" });
  });
});
