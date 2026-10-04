import { afterEach, describe, expect, it, vi } from "vitest";
import { apiFetch, ApiError, registrarProveedorDeToken } from "../client";

function mockFetchOnce(response: Response) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));
}

afterEach(() => {
  vi.unstubAllGlobals();
  registrarProveedorDeToken(async () => null);
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

  it("usa un mensaje legible cuando un error 5xx llega sin detail", async () => {
    // Un 500 no controlado de FastAPI trae el cuerpo en texto plano; antes el
    // usuario veía el statusText crudo: "Internal Server Error".
    mockFetchOnce(
      new Response("Internal Server Error", {
        status: 500,
        statusText: "Internal Server Error",
        headers: { "Content-Type": "text/plain" },
      }),
    );
    const error = await apiFetch("/tenders/recommended").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(500);
    expect((error as ApiError).message).not.toMatch(/Internal Server Error/);
    expect((error as ApiError).message).toMatch(/Inténtalo nuevamente/);
  });

  it("prefiere el detail del backend también en errores 5xx", async () => {
    mockFetchOnce(
      new Response(JSON.stringify({ detail: "No pudimos guardar tus recomendaciones." }), {
        status: 503,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(apiFetch("/tenders/recommended")).rejects.toThrowError(
      expect.objectContaining({ status: 503, message: "No pudimos guardar tus recomendaciones." }),
    );
  });
});

describe("apiFetch — código estable del error", () => {
  it("expone el code y el cuerpo cuando el backend los manda", async () => {
    mockFetchOnce(
      new Response(
        JSON.stringify({ detail: "Tope alcanzado", code: "quota_exceeded", limit: 100 }),
        { status: 403, headers: { "Content-Type": "application/json" } },
      ),
    );

    const error = await apiFetch("/tenders/t/attachments/a/upload-url").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).message).toBe("Tope alcanzado");
    expect((error as ApiError).code).toBe("quota_exceeded");
    expect((error as { body: { limit: number } }).body.limit).toBe(100);
  });

  it("deja code en null cuando el error no trae uno", async () => {
    mockFetchOnce(
      new Response(JSON.stringify({ detail: "No autorizado" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const error = await apiFetch("/auth/me").catch((e: unknown) => e);

    expect((error as ApiError).code).toBeNull();
  });

  it("deja code y body en null cuando la respuesta no es JSON", async () => {
    mockFetchOnce(new Response("caída", { status: 502, statusText: "Bad Gateway" }));

    const error = await apiFetch("/auth/me").catch((e: unknown) => e);

    expect((error as ApiError).code).toBeNull();
    expect((error as ApiError).body).toBeNull();
  });

  it("construir un ApiError con status y mensaje sigue funcionando", () => {
    const error = new ApiError(404, "No existe");

    expect(error.status).toBe(404);
    expect(error.code).toBeNull();
    expect(error.body).toBeNull();
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

describe("apiFetch — token de sesión", () => {
  /**
   * El token va en la cabecera y no en la cookie de Supabase a propósito: esa
   * cookie es un JSON en base64 partido en trozos, y lleva dentro el refresh
   * token. Que el backend lo reciba en `Authorization` es lo que evita tener
   * que reensamblar en Python un formato privado de la librería.
   */
  function espiarFetch() {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    return fetchMock;
  }

  function cabeceras(fetchMock: ReturnType<typeof vi.fn>): Record<string, string> {
    return (fetchMock.mock.calls[0][1] as RequestInit).headers as Record<string, string>;
  }

  it("adjunta el token como Bearer cuando hay sesión", async () => {
    registrarProveedorDeToken(async () => "jwt-de-supabase");
    const fetchMock = espiarFetch();

    await apiFetch<void>("/auth/me");

    expect(cabeceras(fetchMock).Authorization).toBe("Bearer jwt-de-supabase");
  });

  it("no manda la cabecera cuando no hay sesión", async () => {
    const fetchMock = espiarFetch();

    await apiFetch<void>("/auth/me");

    expect(cabeceras(fetchMock).Authorization).toBeUndefined();
  });

  it("respeta la cabecera que ponga quien llama", async () => {
    registrarProveedorDeToken(async () => "jwt-de-supabase");
    const fetchMock = espiarFetch();

    await apiFetch<void>("/auth/me", { headers: { Authorization: "Bearer otro" } });

    expect(cabeceras(fetchMock).Authorization).toBe("Bearer otro");
  });

  it("sigue sin fijar Content-Type cuando el cuerpo es FormData", async () => {
    registrarProveedorDeToken(async () => "jwt-de-supabase");
    const fetchMock = espiarFetch();

    await apiFetch<void>("/upload", { method: "POST", body: new FormData() });

    expect(cabeceras(fetchMock)["Content-Type"]).toBeUndefined();
    expect(cabeceras(fetchMock).Authorization).toBe("Bearer jwt-de-supabase");
  });
});
