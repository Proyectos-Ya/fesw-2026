import { afterEach, describe, expect, it, vi } from "vitest";
import {
  checkRutExists,
  createSupplier,
  getMySupplier,
  getMySupplierOrNull,
  updateSupplier,
} from "../supplierService";
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

describe("getMySupplierOrNull", () => {
  it("devuelve la empresa cuando existe", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ id: "abc-123", ...validData }),
      }),
    );

    const result = await getMySupplierOrNull();

    expect(result).not.toBeNull();
    expect(result?.id).toBe("abc-123");
  });

  it("devuelve null cuando el usuario no tiene empresa (404)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        statusText: "Not Found",
        json: async () => ({ detail: "Sin empresa asociada" }),
      }),
    );

    await expect(getMySupplierOrNull()).resolves.toBeNull();
  });

  it("devuelve null cuando la consulta falla por red", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    );

    await expect(getMySupplierOrNull()).resolves.toBeNull();
  });
});

describe("checkRutExists", () => {
  it("hace GET a /suppliers/rut-exists con el RUT codificado y devuelve true si existe", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ exists: true }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await checkRutExists("76.086.428-5");

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain("/suppliers/rut-exists?rut=76.086.428-5");
    expect(result).toBe(true);
  });

  it("devuelve false cuando el RUT no está registrado", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ exists: false }),
      }),
    );

    await expect(checkRutExists("76.086.428-5")).resolves.toBe(false);
  });
});

describe("updateSupplier", () => {
  it("hace PATCH a /suppliers/me con los campos editados", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: "abc-123", ...validData, legal_name: "Nueva SpA" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await updateSupplier({ legal_name: "Nueva SpA" });

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/suppliers/me");
    expect(options.method).toBe("PATCH");
    expect(options.credentials).toBe("include");
    expect(JSON.parse(options.body as string)).toEqual({ legal_name: "Nueva SpA" });
    expect(result.legal_name).toBe("Nueva SpA");
  });
});
