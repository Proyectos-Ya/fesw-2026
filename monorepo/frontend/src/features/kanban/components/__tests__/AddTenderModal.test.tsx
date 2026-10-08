import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { MatchingResult, Tender } from "@/features/matches/tenderTypes";
import { AddTenderModal } from "../AddTenderModal";

vi.mock("@/features/auth/AuthContext", () => ({
  useAuth: () => ({
    user: { id: "user-1", email: "test@example.com" },
    isLoading: false,
    isAuthenticated: true,
  }),
}));

vi.mock("@/features/matches/services/tenderService", () => ({
  getRecommendedTenders: vi.fn(async () => []),
  getTenderDetail: vi.fn(async () => ({ tender: {} })),
}));

vi.mock("@/features/search/services/searchService", () => ({
  searchTenders: vi.fn(async () => ({ items: [] })),
}));

const fetchSavedTendersMock = vi.fn();

vi.mock("@/features/saved-tenders/services/savedTenders.service", () => ({
  fetchSavedTenders: (...args: unknown[]) => fetchSavedTendersMock(...args),
  saveTenderApi: vi.fn(),
  unsaveTenderApi: vi.fn(),
}));

function makeTender(id: string, name: string): Tender {
  return {
    id,
    code: `COD-${id}`,
    name,
    description: null,
    status_id: 1,
    status_code: "publicada",
    published_at: "2026-06-01T00:00:00Z",
    closing_at: "2026-12-31T00:00:00Z",
    last_change_at: "2026-06-01T00:00:00Z",
    buyer_rut: "999-9",
    buyer_name: "Comprador X",
    buyer_unit: "Unidad",
    region: null,
    province: null,
    commune: null,
    available_amount_clp: null,
    created_at: "2026-06-01T00:00:00Z",
    updated_at: "2026-06-01T00:00:00Z",
    items: [],
  };
}

function makeSavedMatch(tenderId: string, name: string, calculatedAt: string): MatchingResult {
  return {
    id: `match-${tenderId}`,
    supplier_id: "sup-1",
    tender_id: tenderId,
    similarity_score: 80,
    reranker_score: 85,
    final_score: 82,
    model_version: "v1",
    calculated_at: calculatedAt,
    tender: makeTender(tenderId, name),
  };
}

describe("AddTenderModal — tab de guardadas", () => {
  beforeEach(() => {
    fetchSavedTendersMock.mockReset();
  });

  it("Tab Guardadas carga y muestra las licitaciones guardadas", async () => {
    fetchSavedTendersMock.mockResolvedValue([
      makeSavedMatch("tender-A", "Servicio TI guardado", "2026-07-01T00:00:00Z"),
      makeSavedMatch("tender-B", "Insumos oficina guardado", "2026-07-05T00:00:00Z"),
    ]);

    render(
      <AddTenderModal
        columnId="col-1"
        columnName="Por hacer"
        boardTenderIds={[]}
        onAdd={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("Servicio TI guardado")).toBeInTheDocument();
      expect(screen.getByText("Insumos oficina guardado")).toBeInTheDocument();
    });
  });

  it("Oculta de la lista las guardadas que ya están en el tablero", async () => {
    fetchSavedTendersMock.mockResolvedValue([
      makeSavedMatch("tender-A", "Servicio TI guardado", "2026-07-01T00:00:00Z"),
      makeSavedMatch("tender-B", "Insumos oficina guardado", "2026-07-05T00:00:00Z"),
    ]);

    render(
      <AddTenderModal
        columnId="col-1"
        columnName="Por hacer"
        boardTenderIds={["tender-A"]}
        onAdd={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("Insumos oficina guardado")).toBeInTheDocument();
    });
    expect(screen.queryByText("Servicio TI guardado")).not.toBeInTheDocument();
  });

  it("Click en una guardada llama a onAdd con los parámetros correctos", async () => {
    const user = userEvent.setup();
    const onAdd = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();
    fetchSavedTendersMock.mockResolvedValue([
      makeSavedMatch("tender-A", "Servicio TI guardado", "2026-07-01T00:00:00Z"),
    ]);

    render(
      <AddTenderModal
        columnId="col-1"
        columnName="Por hacer"
        boardTenderIds={[]}
        onAdd={onAdd}
        onClose={onClose}
      />,
    );

    const card = await screen.findByText("Servicio TI guardado");
    await user.click(card);

    await waitFor(() => {
      expect(onAdd).toHaveBeenCalledTimes(1);
    });
    const [tenderId, columnId, tender] = onAdd.mock.calls[0];
    expect(tenderId).toBe("tender-A");
    expect(columnId).toBe("col-1");
    expect(tender).toMatchObject({ id: "tender-A", name: "Servicio TI guardado" });
  });
});
