import { afterEach, describe, expect, it, vi } from "vitest";
import {
  describeImportError,
  importCompanyProfile,
  type CompanyProfileImport,
} from "../supplierService";
import { ApiError, TimeoutError } from "@/features/shared/api/client";

const IMPORTED: CompanyProfileImport = {
  source: "web-empresario",
  rut: "76668304-5",
  legal_name: "Planeta Libre Soluciones Sustentables Limitada",
  is_active: true,
  regions: ["Metropolitana"],
  sectors: ["Obras de Construcción e Infraestructura"],
  keywords: ["pintura", "revestimiento"],
  notices: [],
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("importCompanyProfile", () => {
  it("hace GET a /suppliers/profile-import con el RUT codificado", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => IMPORTED });
    vi.stubGlobal("fetch", fetchMock);

    const result = await importCompanyProfile("76.668.304-5");

    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/suppliers/profile-import?rut=76.668.304-5");
    expect(options.credentials).toBe("include");
    expect(result.keywords).toEqual(["pintura", "revestimiento"]);
  });

  it("lanza ApiError con el detail cuando la fuente no tiene datos (404)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        statusText: "Not Found",
        json: async () => ({ detail: "No encontramos datos para el RUT 76668304-5." }),
      }),
    );

    await expect(importCompanyProfile("76.668.304-5")).rejects.toBeInstanceOf(ApiError);
  });
});

describe("describeImportError", () => {
  it("muestra el 404 como aviso informativo con el detalle del backend", () => {
    const err = new ApiError(404, "No encontramos datos para el RUT 76668304-5.");

    expect(describeImportError(err)).toEqual({
      kind: "info",
      message: "No encontramos datos para el RUT 76668304-5.",
    });
  });

  it.each([400, 502, 503])("muestra el %s como advertencia con el detalle del backend", (status) => {
    const err = new ApiError(status, "Detalle en español");

    expect(describeImportError(err)).toEqual({ kind: "warning", message: "Detalle en español" });
  });

  it("muestra el timeout como advertencia", () => {
    const err = new TimeoutError();

    expect(describeImportError(err)).toEqual({ kind: "warning", message: err.message });
  });

  it("usa un mensaje genérico para cualquier otro error", () => {
    const result = describeImportError(new TypeError("Failed to fetch"));

    expect(result.kind).toBe("warning");
    expect(result.message).toMatch(/no pudimos importar/i);
  });
});
