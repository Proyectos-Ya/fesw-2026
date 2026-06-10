import { afterEach, describe, expect, it, vi } from "vitest";
import { createSupplier, getMySupplier } from "../supplierService";
import { ApiError, TimeoutError } from "@/features/shared/api/client";
import type { ProfileData } from "../../profileSchema";

const validData: ProfileData = {
  legal_name: "Constructora Demo SpA",
  rut: "12.345.678-5",
  regions: ["Metropolitana de Santiago"],
  years_experience: 5,
  num_employees: 20,
  sectors: ["Construcción"],
  keywords: ["obras", "edificación"],
  certifications: ["ISO 9001"],
  description: "Empresa con amplia experiencia en obras civiles y edificación.",
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("createSupplier", () => {
  it("hace POST a /suppliers/ con los datos del perfil y devuelve el proveedor creado", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: "abc-123", ...validData }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await createSupplier(validData);

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/suppliers/");
    expect(options.method).toBe("POST");
    expect(options.credentials).toBe("include");
    expect(JSON.parse(options.body as string)).toMatchObject(validData);
    expect(result.id).toBe("abc-123");
  });

  it("lanza TimeoutError cuando el servidor no responde en 60 segundos", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new DOMException("signal aborted", "AbortError")),
    );

    await expect(createSupplier(validData)).rejects.toBeInstanceOf(TimeoutError);
  });

  it("lanza ApiError con el detail del backend cuando el RUT ya existe (409)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 409,
        statusText: "Conflict",
        json: async () => ({ detail: "El proveedor ya existe" }),
      }),
    );

    await expect(createSupplier(validData)).rejects.toBeInstanceOf(ApiError);
    await expect(createSupplier(validData)).rejects.toMatchObject({
      status: 409,
      message: "El proveedor ya existe",
    });
  });
});

describe("getMySupplier", () => {
  it("hace GET a /suppliers/me con credenciales y devuelve la empresa", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: "abc-123", ...validData }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await getMySupplier();

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/suppliers/me");
    expect(options.credentials).toBe("include");
    expect(result.id).toBe("abc-123");
  });

  it("lanza ApiError 404 cuando el usuario no tiene empresa", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        statusText: "Not Found",
        json: async () => ({ detail: "Sin empresa asociada" }),
      }),
    );

    await expect(getMySupplier()).rejects.toMatchObject({
      status: 404,
      message: "Sin empresa asociada",
    });
  });
});
