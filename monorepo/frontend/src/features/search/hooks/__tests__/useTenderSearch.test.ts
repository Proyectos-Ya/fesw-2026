import { renderHook, act, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  useTenderSearch,
  SEARCH_STORAGE_KEY,
  SEARCH_REGIONS_PREFILLED_KEY,
} from "../useTenderSearch";
import * as searchService from "../../services/searchService";
import * as savedService from "@/features/saved-tenders/services/savedTenders.service";
import * as supplierService from "@/features/company-profile/services/supplierService";
import { SAVED_TENDERS_ERRORS } from "@/features/saved-tenders/constants";
import type { TenderSearchResult } from "../../types";

const replaceMock = vi.fn();
let mockSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: replaceMock,
    push: vi.fn(),
  }),
  usePathname: () => "/buscar",
  useSearchParams: () => mockSearchParams,
}));

vi.mock("../../services/searchService");
vi.mock("@/features/saved-tenders/services/savedTenders.service");
vi.mock("@/features/company-profile/services/supplierService");

const mockSearchResult: TenderSearchResult = {
  items: [
    {
      id: "tender-1",
      code: "111-22-COT26",
      name: "Compra de Insumos",
      description: "Prueba",
      status_id: 1,
      status_code: "publicada",
      published_at: "2026-06-01T00:00:00Z",
      closing_at: "2026-06-15T00:00:00Z",
      last_change_at: "2026-06-01T00:00:00Z",
      buyer_rut: "111-1",
      buyer_name: "Municipalidad",
      buyer_unit: "Salud",
      region: "Valparaíso",
      province: "Valparaíso",
      commune: "Valparaíso",
      available_amount_clp: 1000000,
      created_at: "2026-06-01T00:00:00Z",
      updated_at: "2026-06-01T00:00:00Z",
      items: [],
    },
  ],
  total: 1,
  is_truncated: false,
};

beforeEach(() => {
  vi.clearAllMocks();
  mockSearchParams = new URLSearchParams();
  window.sessionStorage.clear();
  vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([]);
  vi.mocked(searchService.searchTenders).mockResolvedValue(mockSearchResult);
  vi.mocked(supplierService.getMySupplierOrNull).mockResolvedValue(null);
});

/** Empresa con solo lo que mira el buscador: dónde declaró que opera. */
function empresaConRegiones(regions: string[]) {
  return { regions } as Awaited<
    ReturnType<typeof supplierService.getMySupplier>
  >;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useTenderSearch", () => {
  it("inicia cargando y obtiene resultados de búsqueda", async () => {
    const { result } = renderHook(() => useTenderSearch());

    expect(result.current.state.isLoading).toBe(true);

    await waitFor(() => expect(result.current.state.isLoading).toBe(false));

    expect(result.current.state.items).toHaveLength(1);
    expect(result.current.state.total).toBe(1);
    expect(result.current.state.error).toBeNull();
  });

  it("restaura los parámetros desde sessionStorage al montar con URL limpia (CA-8)", () => {
    window.sessionStorage.setItem(SEARCH_STORAGE_KEY, "q=hospital&availability=vigentes");
    mockSearchParams = new URLSearchParams();

    renderHook(() => useTenderSearch());

    expect(replaceMock).toHaveBeenCalledWith(
      "/buscar?q=hospital&availability=vigentes",
      { scroll: false },
    );
  });

  it("guarda los parámetros en sessionStorage al actualizar la búsqueda", () => {
    const { result } = renderHook(() => useTenderSearch());

    act(() => {
      result.current.setRegions(["Valparaíso"]);
    });

    const stored = window.sessionStorage.getItem(SEARCH_STORAGE_KEY);
    expect(stored).toContain("regions=Valpara%C3%ADso");
  });

  it("actualiza la URL tras el debounce cuando el usuario escribe en el input", async () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useTenderSearch());

    act(() => {
      result.current.setInputText("equipamiento");
    });

    expect(result.current.inputText).toBe("equipamiento");
    expect(replaceMock).not.toHaveBeenCalled();

    // Avanzar debounce time
    act(() => {
      vi.advanceTimersByTime(400);
    });

    expect(replaceMock).toHaveBeenCalledWith("/buscar?q=equipamiento", { scroll: false });
    vi.useRealTimers();
  });

  it("actualiza la URL al seleccionar regiones", () => {
    const { result } = renderHook(() => useTenderSearch());

    act(() => {
      result.current.setRegions(["Valparaíso", "Tarapacá"]);
    });

    expect(replaceMock).toHaveBeenCalledWith(
      "/buscar?regions=Valpara%C3%ADso&regions=Tarapac%C3%A1",
      { scroll: false },
    );
  });

  it("actualiza la URL al seleccionar disponibilidad", () => {
    const { result } = renderHook(() => useTenderSearch());

    act(() => {
      result.current.setAvailability("vigentes");
    });

    expect(replaceMock).toHaveBeenCalledWith(
      "/buscar?availability=vigentes",
      { scroll: false },
    );
  });

  it("envía closing_from cuando availability es vigentes", async () => {
    mockSearchParams = new URLSearchParams("availability=vigentes");
    renderHook(() => useTenderSearch());

    await waitFor(() => {
      expect(searchService.searchTenders).toHaveBeenCalledWith(
        expect.objectContaining({
          closing_from: expect.any(String),
        }),
      );
    });
  });

  it("envía closing_to cuando availability es cerradas", async () => {
    mockSearchParams = new URLSearchParams("availability=cerradas");
    renderHook(() => useTenderSearch());

    await waitFor(() => {
      expect(searchService.searchTenders).toHaveBeenCalledWith(
        expect.objectContaining({
          closing_to: expect.any(String),
        }),
      );
    });
  });

  it("limpia todos los filtros y remueve sessionStorage al llamar a clearFilters", () => {
    window.sessionStorage.setItem(SEARCH_STORAGE_KEY, "q=hospital");
    mockSearchParams = new URLSearchParams("q=hospital&regions=Valparaíso");
    const { result } = renderHook(() => useTenderSearch());

    act(() => {
      result.current.clearFilters();
    });

    expect(result.current.inputText).toBe("");
    expect(window.sessionStorage.getItem(SEARCH_STORAGE_KEY)).toBeNull();
    expect(replaceMock).toHaveBeenCalledWith("/buscar", { scroll: false });
  });

  it("actualiza la URL y sessionStorage al definir rango explícito de fechas (CA-1)", () => {
    const { result } = renderHook(() => useTenderSearch());

    act(() => {
      result.current.setClosingDateRange("2026-09-01", "2026-09-15");
    });

    expect(replaceMock).toHaveBeenCalledWith(
      "/buscar?closing_from=2026-09-01&closing_to=2026-09-15",
      { scroll: false },
    );
    const stored = window.sessionStorage.getItem(SEARCH_STORAGE_KEY);
    expect(stored).toContain("closing_from=2026-09-01");
    expect(stored).toContain("closing_to=2026-09-15");
  });

  it("envía closing_from y closing_to en ISO al servicio cuando están en URL (CA-1)", async () => {
    mockSearchParams = new URLSearchParams("closing_from=2026-09-01&closing_to=2026-09-15");
    renderHook(() => useTenderSearch());

    await waitFor(() => {
      expect(searchService.searchTenders).toHaveBeenCalledWith(
        expect.objectContaining({
          closing_from: "2026-09-01T00:00:00Z",
          closing_to: "2026-09-15T23:59:59Z",
        }),
      );
    });
  });

  it("parsea province_id y commune_id desde URL searchParams como enteros", () => {
    mockSearchParams = new URLSearchParams("province_id=51&commune_id=295");
    const { result } = renderHook(() => useTenderSearch());

    expect(result.current.provinceId).toBe(51);
    expect(result.current.communeId).toBe(295);
    expect(result.current.activeFilterCount).toBe(2);
    expect(result.current.hasActiveFilters).toBe(true);
  });

  it("actualiza la URL y sessionStorage al seleccionar provincia y resetea comuna", () => {
    mockSearchParams = new URLSearchParams("province_id=51&commune_id=295");
    const { result } = renderHook(() => useTenderSearch());

    act(() => {
      result.current.setProvinceId(52);
    });

    expect(replaceMock).toHaveBeenCalledWith(
      "/buscar?province_id=52",
      { scroll: false },
    );
    const stored = window.sessionStorage.getItem(SEARCH_STORAGE_KEY);
    expect(stored).toContain("province_id=52");
    expect(stored).not.toContain("commune_id");
  });

  it("actualiza la URL y sessionStorage al seleccionar comuna", () => {
    mockSearchParams = new URLSearchParams("province_id=51");
    const { result } = renderHook(() => useTenderSearch());

    act(() => {
      result.current.setCommuneId(295);
    });

    expect(replaceMock).toHaveBeenCalledWith(
      "/buscar?province_id=51&commune_id=295",
      { scroll: false },
    );
    const stored = window.sessionStorage.getItem(SEARCH_STORAGE_KEY);
    expect(stored).toContain("commune_id=295");
  });

  it("resetea province_id y commune_id al cambiar regiones", () => {
    mockSearchParams = new URLSearchParams("regions=Metropolitana&province_id=51&commune_id=295");
    const { result } = renderHook(() => useTenderSearch());

    act(() => {
      result.current.setRegions(["Valparaíso"]);
    });

    expect(replaceMock).toHaveBeenCalledWith(
      "/buscar?regions=Valpara%C3%ADso",
      { scroll: false },
    );
    const stored = window.sessionStorage.getItem(SEARCH_STORAGE_KEY);
    expect(stored).not.toContain("province_id");
    expect(stored).not.toContain("commune_id");
  });

  it("envía province_id y commune_id al servicio de búsqueda cuando están en la URL", async () => {
    mockSearchParams = new URLSearchParams("province_id=51&commune_id=295");
    renderHook(() => useTenderSearch());

    await waitFor(() => {
      expect(searchService.searchTenders).toHaveBeenCalledWith(
        expect.objectContaining({
          province_id: 51,
          commune_id: 295,
        }),
      );
    });
  });

  describe("handleToggleSave (CA-5)", () => {
    it("aplica rollback restaurando el estado previo y notifica ante fallo al guardar licitación", async () => {
      vi.mocked(savedService.saveTenderApi).mockRejectedValue(
        new TypeError("Failed to fetch"),
      );

      const { result } = renderHook(() => useTenderSearch());

      await waitFor(() => {
        expect(result.current.state.isLoading).toBe(false);
      });

      expect(result.current.savedTenderIds.has("tender-1")).toBe(false);

      await act(async () => {
        await result.current.toggleSave("tender-1");
      });

      // Rollback verificado
      expect(result.current.savedTenderIds.has("tender-1")).toBe(false);
      expect(result.current.actionError).toBe(SAVED_TENDERS_ERRORS.SAVE_FAILED);
    });

    it("aplica rollback restaurando el estado previo y notifica ante fallo al quitar licitación guardada", async () => {
      vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([
        {
          id: "match-1",
          supplier_id: "s-1",
          tender_id: "tender-1",
          similarity_score: 80,
          reranker_score: 80,
          final_score: 80,
          model_version: "v1",
          calculated_at: "2026-06-01T00:00:00Z",
          tender: {
            id: "tender-1",
            code: "111-22-COT26",
            name: "Compra de Insumos",
            description: "Prueba",
            status_id: 1,
            status_code: "publicada",
            published_at: "2026-06-01T00:00:00Z",
            closing_at: "2026-06-15T00:00:00Z",
            last_change_at: "2026-06-01T00:00:00Z",
            buyer_rut: "111-1",
            buyer_name: "Municipalidad",
            buyer_unit: "Salud",
            region: "Valparaíso",
            province: "Valparaíso",
            commune: "Valparaíso",
            available_amount_clp: 1000000,
            created_at: "2026-06-01T00:00:00Z",
            updated_at: "2026-06-01T00:00:00Z",
            items: [],
          },
        },
      ]);
      vi.mocked(savedService.unsaveTenderApi).mockRejectedValue(
        new TypeError("Failed to fetch"),
      );

      const { result } = renderHook(() => useTenderSearch());

      await waitFor(() => {
        expect(result.current.savedTenderIds.has("tender-1")).toBe(true);
      });

      await act(async () => {
        await result.current.toggleSave("tender-1");
      });

      // Rollback verificado: la licitación sigue guardada
      expect(result.current.savedTenderIds.has("tender-1")).toBe(true);
      expect(result.current.actionError).toBe(SAVED_TENDERS_ERRORS.UNSAVE_FAILED);
    });
  });
});

describe("useTenderSearch: regiones de la empresa por defecto", () => {
  it("parte con las regiones del perfil cuando no hay búsqueda previa", async () => {
    vi.mocked(supplierService.getMySupplierOrNull).mockResolvedValue(
      empresaConRegiones(["Metropolitana", "Valparaíso"])
    );

    renderHook(() => useTenderSearch());

    await waitFor(() => expect(replaceMock).toHaveBeenCalled());
    // "Metropolitana" es como lo escribe el perfil; el buscador exige el
    // nombre canónico y responde 422 con cualquier otro.
    expect(replaceMock).toHaveBeenCalledWith(
      "/buscar?regions=Metropolitana+de+Santiago&regions=Valpara%C3%ADso",
      { scroll: false }
    );
    expect(window.sessionStorage.getItem(SEARCH_STORAGE_KEY)).toContain(
      "Metropolitana+de+Santiago"
    );
  });

  it("no pisa una búsqueda guardada", async () => {
    window.sessionStorage.setItem(SEARCH_STORAGE_KEY, "q=aseo");
    vi.mocked(supplierService.getMySupplierOrNull).mockResolvedValue(
      empresaConRegiones(["Metropolitana"])
    );

    renderHook(() => useTenderSearch());

    await waitFor(() => expect(replaceMock).toHaveBeenCalled());
    expect(replaceMock).toHaveBeenCalledWith("/buscar?q=aseo", { scroll: false });
    expect(supplierService.getMySupplierOrNull).not.toHaveBeenCalled();
  });

  it("no las repone después de que el usuario las quitó", async () => {
    // Limpiar filtros deja la URL y la búsqueda guardada vacías, igual que al
    // llegar por primera vez: sin la marca, volver acá las repondría.
    window.sessionStorage.setItem(SEARCH_REGIONS_PREFILLED_KEY, "1");
    vi.mocked(supplierService.getMySupplierOrNull).mockResolvedValue(
      empresaConRegiones(["Metropolitana"])
    );

    renderHook(() => useTenderSearch());

    await waitFor(() =>
      expect(searchService.searchTenders).toHaveBeenCalled()
    );
    expect(supplierService.getMySupplierOrNull).not.toHaveBeenCalled();
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("no toca la URL si la empresa no declaró regiones", async () => {
    vi.mocked(supplierService.getMySupplierOrNull).mockResolvedValue(
      empresaConRegiones([])
    );

    renderHook(() => useTenderSearch());

    await waitFor(() =>
      expect(
        window.sessionStorage.getItem(SEARCH_REGIONS_PREFILLED_KEY)
      ).toBe("1")
    );
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("no rompe la búsqueda si el usuario todavía no tiene empresa", async () => {
    vi.mocked(supplierService.getMySupplierOrNull).mockResolvedValue(null);

    const { result } = renderHook(() => useTenderSearch());

    await waitFor(() => expect(result.current.state.isLoading).toBe(false));
    expect(result.current.state.items).toHaveLength(1);
    expect(replaceMock).not.toHaveBeenCalled();
  });
});
