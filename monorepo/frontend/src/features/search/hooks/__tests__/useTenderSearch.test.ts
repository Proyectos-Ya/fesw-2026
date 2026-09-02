import { renderHook, act, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useTenderSearch, SEARCH_STORAGE_KEY } from "../useTenderSearch";
import * as searchService from "../../services/searchService";
import * as savedService from "@/features/saved-tenders/services/savedTenders.service";
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
});

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
});
