import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as client from "@/features/shared/api/client";
import {
  clearLocationCatalogCache,
  getLocationCatalog,
} from "../locationCatalogService";
import type { LocationCatalogResponse } from "../../types";

const mockCatalog: LocationCatalogResponse = {
  provinces: [
    { id: 51, name: "Santiago", region_name: "Metropolitana de Santiago" },
    { id: 52, name: "Cordillera", region_name: "Metropolitana de Santiago" },
  ],
  communes: [
    { id: 295, name: "Santiago", province_name: "Santiago" },
    { id: 296, name: "Providencia", province_name: "Santiago" },
    { id: 300, name: "Puente Alto", province_name: "Cordillera" },
  ],
};

describe("locationCatalogService", () => {
  beforeEach(() => {
    clearLocationCatalogCache();
    window.sessionStorage.clear();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    clearLocationCatalogCache();
    window.sessionStorage.clear();
  });

  it("llama a GET /catalogs/locations cuando la caché está vacía", async () => {
    const apiFetchSpy = vi
      .spyOn(client, "apiFetch")
      .mockResolvedValueOnce(mockCatalog);

    const data = await getLocationCatalog();

    expect(apiFetchSpy).toHaveBeenCalledWith("/catalogs/locations");
    expect(data).toEqual(mockCatalog);
  });

  it("utiliza la caché en memoria y no vuelve a llamar a la API en llamadas subsecuentes", async () => {
    const apiFetchSpy = vi
      .spyOn(client, "apiFetch")
      .mockResolvedValueOnce(mockCatalog);

    const first = await getLocationCatalog();
    const second = await getLocationCatalog();

    expect(apiFetchSpy).toHaveBeenCalledOnce();
    expect(first).toBe(mockCatalog);
    expect(second).toBe(mockCatalog);
  });

  it("guarda el catálogo en sessionStorage para persistencia en sesión", async () => {
    vi.spyOn(client, "apiFetch").mockResolvedValueOnce(mockCatalog);

    await getLocationCatalog();

    const stored = window.sessionStorage.getItem("proyectosya_locations_catalog");
    expect(stored).not.toBeNull();
    expect(JSON.parse(stored!)).toEqual(mockCatalog);
  });

  it("recupera el catálogo desde sessionStorage si existe sin llamar a la API", async () => {
    window.sessionStorage.setItem(
      "proyectosya_locations_catalog",
      JSON.stringify(mockCatalog),
    );
    const apiFetchSpy = vi.spyOn(client, "apiFetch");

    const data = await getLocationCatalog();

    expect(apiFetchSpy).not.toHaveBeenCalled();
    expect(data).toEqual(mockCatalog);
  });

  it("permite reintentar si la llamada previa falló", async () => {
    const apiFetchSpy = vi
      .spyOn(client, "apiFetch")
      .mockRejectedValueOnce(new Error("Network Error"))
      .mockResolvedValueOnce(mockCatalog);

    await expect(getLocationCatalog()).rejects.toThrow("Network Error");
    const retryData = await getLocationCatalog();

    expect(apiFetchSpy).toHaveBeenCalledTimes(2);
    expect(retryData).toEqual(mockCatalog);
  });

  it("limpia la memoria y sessionStorage al llamar a clearLocationCatalogCache", async () => {
    const apiFetchSpy = vi
      .spyOn(client, "apiFetch")
      .mockResolvedValue(mockCatalog);

    await getLocationCatalog();
    expect(apiFetchSpy).toHaveBeenCalledTimes(1);

    clearLocationCatalogCache();
    expect(window.sessionStorage.getItem("proyectosya_locations_catalog")).toBeNull();

    await getLocationCatalog();
    expect(apiFetchSpy).toHaveBeenCalledTimes(2);
  });
});
