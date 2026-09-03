import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useLocationCatalog } from "../useLocationCatalog";
import * as catalogService from "../../services/locationCatalogService";
import type { LocationCatalogResponse } from "../../types";

const mockCatalog: LocationCatalogResponse = {
  provinces: [
    { id: 51, name: "Santiago", region_name: "Metropolitana de Santiago" },
    { id: 52, name: "Cordillera", region_name: "Metropolitana de Santiago" },
  ],
  communes: [
    { id: 295, name: "Santiago", province_name: "Santiago" },
    { id: 296, name: "Providencia", province_name: "Santiago" },
  ],
};

describe("useLocationCatalog", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("obtiene las provincias y comunas correctamente", async () => {
    vi.spyOn(catalogService, "getLocationCatalog").mockResolvedValueOnce(mockCatalog);

    const { result } = renderHook(() => useLocationCatalog());

    expect(result.current.isLoading).toBe(true);
    expect(result.current.provinces).toEqual([]);
    expect(result.current.communes).toEqual([]);

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.provinces).toEqual(mockCatalog.provinces);
    expect(result.current.communes).toEqual(mockCatalog.communes);
    expect(result.current.error).toBeNull();
  });

  it("gestiona errores al obtener el catálogo", async () => {
    vi.spyOn(catalogService, "getLocationCatalog").mockRejectedValueOnce(
      new Error("Fallo de red"),
    );

    const { result } = renderHook(() => useLocationCatalog());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.error).toBe("Fallo de red");
    expect(result.current.provinces).toEqual([]);
    expect(result.current.communes).toEqual([]);
  });
});
