import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SearchDashboard } from "../SearchDashboard";
import * as searchService from "../../services/searchService";
import * as savedService from "@/features/saved-tenders/services/savedTenders.service";
import { ApiError } from "@/features/shared/api/client";
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
      name: "Compra de Insumos Médicos",
      description: "Prueba de licitación",
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
    },
  ],
  total: 1,
  is_truncated: false,
};

beforeEach(() => {
  vi.clearAllMocks();
  mockSearchParams = new URLSearchParams();
  vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([]);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("SearchDashboard", () => {
  it("renderiza la lista de licitaciones al recibir resultados", async () => {
    vi.mocked(searchService.searchTenders).mockResolvedValue(mockSearchResult);

    render(<SearchDashboard />);

    await waitFor(() => {
      expect(screen.getByText("Compra de Insumos Médicos")).toBeInTheDocument();
      expect(screen.getByText("Hospital San Juan")).toBeInTheDocument();
    });

    expect(screen.getByText("Se encontró 1 licitación.")).toBeInTheDocument();
  });

  it("renderiza el empty state cuando no hay coincidencias", async () => {
    mockSearchParams = new URLSearchParams("q=palabraInexistente");
    vi.mocked(searchService.searchTenders).mockResolvedValue({
      items: [],
      total: 0,
      is_truncated: false,
    });

    render(<SearchDashboard />);

    await waitFor(() => {
      expect(
        screen.getByText("Sin resultados para tu búsqueda"),
      ).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: /limpiar filtros/i })).toBeInTheDocument();
  });

  it("muestra banner de aviso si los resultados fueron truncados (HdU 07.4)", async () => {
    vi.mocked(searchService.searchTenders).mockResolvedValue({
      items: mockSearchResult.items,
      total: 600,
      is_truncated: true,
    });

    render(<SearchDashboard />);

    await waitFor(() => {
      expect(
        screen.getByText(/Se superó el límite de resultados para esta consulta/),
      ).toBeInTheDocument();
    });
  });

  it("muestra banner de error no bloqueante y botón reintentar ante falla 503 (HdU 07.5)", async () => {
    vi.mocked(searchService.searchTenders).mockRejectedValue(
      new ApiError(503, "No se pudo completar la búsqueda"),
    );

    render(<SearchDashboard />);

    await waitFor(() => {
      expect(
        screen.getByText("El motor de búsqueda no está disponible en este momento."),
      ).toBeInTheDocument();
    });

    const retryButton = screen.getByRole("button", { name: /reintentar/i });
    expect(retryButton).toBeInTheDocument();

    // Intentar de nuevo y responder con éxito
    vi.mocked(searchService.searchTenders).mockResolvedValue(mockSearchResult);
    fireEvent.click(retryButton);

    await waitFor(() => {
      expect(screen.getByText("Compra de Insumos Médicos")).toBeInTheDocument();
    });
  });
});
