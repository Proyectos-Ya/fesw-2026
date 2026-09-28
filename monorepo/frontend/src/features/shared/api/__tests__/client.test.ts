import { afterEach, describe, expect, it, vi } from "vitest";
import { apiDownload, apiFetch, ApiError, registrarProveedorDeToken } from "../client";

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

  it("expone el code del backend para distinguir errores con el mismo status", async () => {
    // Un enlace caducado y uno revocado son los dos 410 (HdU 19).
    mockFetchOnce(
      new Response(
        JSON.stringify({ detail: "El enlace fue revocado.", code: "share_link_revoked" }),
        { status: 410, headers: { "Content-Type": "application/json" } },
      ),
    );
    await expect(apiFetch("/shared/abc")).rejects.toThrowError(
      expect.objectContaining({ status: 410, code: "share_link_revoked" }),
    );
  });

  it("deja code sin definir cuando el backend no lo manda", async () => {
    mockFetchOnce(
      new Response(JSON.stringify({ detail: "No autorizado" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const error = await apiFetch("/auth/me").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBeUndefined();
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

describe("apiDownload", () => {
  it("con 200 entrega el archivo y el nombre de Content-Disposition", async () => {
    mockFetchOnce(
      new Response("%PDF", {
        status: 200,
        headers: {
          "Content-Type": "application/pdf",
          "Content-Disposition": 'attachment; filename="licitacion-COT26.pdf"',
        },
      }),
    );

    const resultado = await apiDownload("/tenders/t-1/exports", { method: "POST" });

    expect(resultado.kind).toBe("file");
    if (resultado.kind !== "file") return;
    expect(resultado.filename).toBe("licitacion-COT26.pdf");
    await expect(resultado.blob.text()).resolves.toBe("%PDF");
  });

  it("sin Content-Disposition deja el nombre en null", async () => {
    mockFetchOnce(new Response("x", { status: 200 }));

    const resultado = await apiDownload("/exports/j-1/file");

    expect(resultado).toMatchObject({ kind: "file", filename: null });
  });

  it("con 202 devuelve el cuerpo JSON: el archivo sigue generándose", async () => {
    mockFetchOnce(
      new Response(JSON.stringify({ job_id: "j-1", status: "processing" }), {
        status: 202,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const resultado = await apiDownload("/tenders/t-1/exports", { method: "POST" });

    expect(resultado).toEqual({
      kind: "accepted",
      body: { job_id: "j-1", status: "processing" },
    });
  });

  it("normaliza los errores igual que apiFetch", async () => {
    mockFetchOnce(
      new Response(JSON.stringify({ detail: "El archivo venció.", code: "export_expired" }), {
        status: 410,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(apiDownload("/exports/j-1/file")).rejects.toThrowError(
      expect.objectContaining({ status: 410, code: "export_expired", message: "El archivo venció." }),
    );
  });

  it("adjunta el token de sesión", async () => {
    registrarProveedorDeToken(async () => "tok-123");
    const fetchMock = vi.fn().mockResolvedValue(new Response("x", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await apiDownload("/exports/j-1/file");

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer tok-123");
  });
});
