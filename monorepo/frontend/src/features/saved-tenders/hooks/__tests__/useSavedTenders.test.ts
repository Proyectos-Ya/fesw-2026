import { renderHook, act, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useSavedTenders } from "../useSavedTenders";
import * as savedService from "../../services/savedTenders.service";
import { SAVED_TENDERS_ERRORS } from "../../constants";
import { ApiError } from "@/features/shared/api/client";
import type { MatchingResult } from "@/features/matches/tenderTypes";

vi.mock("../../services/savedTenders.service", () => ({
  fetchSavedTenders: vi.fn(),
  saveTenderApi: vi.fn(),
  unsaveTenderApi: vi.fn(),
}));

const mockTenderItem: MatchingResult = {
  id: "match-1",
  supplier_id: "supplier-1",
  tender_id: "tender-1",
  similarity_score: 85,
  reranker_score: 90,
  final_score: 88,
  model_version: "v1.0",
  calculated_at: "2026-06-01T00:00:00Z",
  tender: {
    id: "tender-1",
    code: "111-22-COT26",
    name: "Licitación Insumos Médicos",
    description: "Descripción de prueba",
    status_id: 1,
    status_code: "publicada",
    published_at: "2026-06-01T00:00:00Z",
    closing_at: "2026-06-15T00:00:00Z",
    last_change_at: "2026-06-01T00:00:00Z",
    buyer_rut: "111-1",
    buyer_name: "Hospital San Juan",
    buyer_unit: "Salud",
    region: "Región Metropolitana de Santiago",
    province: "Santiago",
    commune: "Santiago",
    available_amount_clp: 1000000,
    created_at: "2026-06-01T00:00:00Z",
    updated_at: "2026-06-01T00:00:00Z",
    items: [],
    is_saved: true,
  },
};

describe("useSavedTenders (CA-5: Manejo de errores de conexión y rollback)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("carga licitaciones guardadas al inicializar", async () => {
    vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([mockTenderItem]);

    const { result } = renderHook(() => useSavedTenders());

    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.savedTenders).toEqual([mockTenderItem]);
    expect(result.current.isSaved("tender-1")).toBe(true);
    expect(result.current.error).toBeNull();
  });

  it("maneja error en la carga inicial de licitaciones", async () => {
    vi.mocked(savedService.fetchSavedTenders).mockRejectedValue(
      new Error("Fallo de conexión al cargar"),
    );

    const { result } = renderHook(() => useSavedTenders());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).toBe("Fallo de conexión al cargar");
    expect(result.current.savedTenders).toEqual([]);
  });

  describe("Guardar licitación (isCurrentlySaved = false)", () => {
    it("aplica rollback restaurando el estado previo y notifica ante fallo de conexión (TypeError)", async () => {
      vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([]);
      vi.mocked(savedService.saveTenderApi).mockRejectedValue(
        new TypeError("Failed to fetch"),
      );

      const { result } = renderHook(() => useSavedTenders());

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.savedTenders).toHaveLength(0);
      expect(result.current.isSaved("tender-2")).toBe(false);

      await act(async () => {
        await result.current.toggleSave("tender-2", false);
      });

      // Debe haber vuelto al estado anterior (vacío)
      expect(result.current.savedTenders).toHaveLength(0);
      expect(result.current.isSaved("tender-2")).toBe(false);

      // Notificación clara al usuario de que la operación falló y se mantuvo el estado anterior
      expect(result.current.toastMessage).toBe(SAVED_TENDERS_ERRORS.SAVE_FAILED);
      expect(result.current.toastMessage).toMatch(
        /la operación no pudo realizarse y se mantuvo el estado anterior/i,
      );
    });

    it("aplica rollback restaurando el estado previo y notifica ante error HTTP 500 del servidor", async () => {
      vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([]);
      vi.mocked(savedService.saveTenderApi).mockRejectedValue(
        new ApiError(500, "Internal Server Error"),
      );

      const { result } = renderHook(() => useSavedTenders());

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      await act(async () => {
        await result.current.toggleSave("tender-2", false);
      });

      expect(result.current.savedTenders).toHaveLength(0);
      expect(result.current.isSaved("tender-2")).toBe(false);
      expect(result.current.toastMessage).toBe(SAVED_TENDERS_ERRORS.SAVE_FAILED);
    });
  });

  describe("Eliminar / Quitar licitación (isCurrentlySaved = true)", () => {
    it("aplica rollback restaurando el estado previo y notifica ante fallo de conexión de red", async () => {
      vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([mockTenderItem]);
      vi.mocked(savedService.unsaveTenderApi).mockRejectedValue(
        new TypeError("Network connection lost"),
      );

      const { result } = renderHook(() => useSavedTenders());

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.savedTenders).toHaveLength(1);
      expect(result.current.isSaved("tender-1")).toBe(true);

      await act(async () => {
        await result.current.toggleSave("tender-1", true);
      });

      // El estado previo debe preservarse tras la falla (rollback)
      expect(result.current.savedTenders).toHaveLength(1);
      expect(result.current.savedTenders[0]?.id).toBe("match-1");
      expect(result.current.isSaved("tender-1")).toBe(true);

      // Notificación correspondiente
      expect(result.current.toastMessage).toBe(SAVED_TENDERS_ERRORS.UNSAVE_FAILED);
      expect(result.current.toastMessage).toMatch(
        /la operación no pudo realizarse y se mantuvo el estado anterior/i,
      );
    });

    it("aplica rollback restaurando el estado previo y notifica ante error HTTP 503", async () => {
      vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([mockTenderItem]);
      vi.mocked(savedService.unsaveTenderApi).mockRejectedValue(
        new ApiError(503, "Service Unavailable"),
      );

      const { result } = renderHook(() => useSavedTenders());

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      await act(async () => {
        await result.current.toggleSave("tender-1", true);
      });

      expect(result.current.savedTenders).toHaveLength(1);
      expect(result.current.isSaved("tender-1")).toBe(true);
      expect(result.current.toastMessage).toBe(SAVED_TENDERS_ERRORS.UNSAVE_FAILED);
    });
  });

  it("permite limpiar el mensaje de notificación con clearToast", async () => {
    vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([]);
    vi.mocked(savedService.saveTenderApi).mockRejectedValue(
      new Error("Connection error"),
    );

    const { result } = renderHook(() => useSavedTenders());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.toggleSave("tender-99", false);
    });

    expect(result.current.toastMessage).not.toBeNull();

    act(() => {
      result.current.clearToast();
    });

    expect(result.current.toastMessage).toBeNull();
  });
});
