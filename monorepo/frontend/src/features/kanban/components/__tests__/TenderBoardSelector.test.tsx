import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TenderBoardSelector } from "../TenderBoardSelector";
import type { KanbanCard, KanbanColumn } from "../../kanbanTypes";

// El selector consume `useKanban` para enterarse de columnas y tarjetas y para
// disparar las acciones. Mockeamos el hook entero: cada caso describe un
// estado del tablero sin tocar red.
const useKanbanMock = vi.fn();

vi.mock("../../hooks/useKanban", () => ({
  useKanban: () => useKanbanMock(),
}));

// `next/navigation` solo se usa para el CTA "Crear tablero" cuando no se
// pasa `onNavigateToBoard`. Lo mockeamos para evitar depender del App Router.
const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

// `addCard` necesita un `Tender` completo; el componente lo pide por detalle.
// Devolvemos un stub mínimo: los tests solo verifican el flujo, no el payload.
vi.mock("@/features/matches/services/tenderService", () => ({
  getTenderDetail: vi.fn().mockResolvedValue({
    tender: { id: "tender-123", code: "T-1", name: "Tender", items: [] },
    is_closed: false,
    score_pct: null,
  }),
}));

function column(overrides: Partial<KanbanColumn> = {}): KanbanColumn {
  return {
    id: "col1",
    name: "Por postular",
    position: 0,
    color: "#A99A7C",
    card_count: 0,
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function card(overrides: Partial<KanbanCard> = {}): KanbanCard {
  return {
    id: "card1",
    tender_id: "tender-123",
    column_id: "col1",
    position: 0,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    board_entered_at: "2026-01-01T00:00:00Z",
    archived_at: null,
    archived_reason: null,
    ...overrides,
  };
}

describe("TenderBoardSelector", () => {
  beforeEach(() => {
    useKanbanMock.mockReset();
    pushMock.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("muestra loading cuando columnas aún no cargan", () => {
    useKanbanMock.mockReturnValue({
      columns: [],
      cards: [],
      loading: true,
      addCard: vi.fn(),
      moveCard: vi.fn(),
      archiveCard: vi.fn(),
    });

    render(<TenderBoardSelector tenderId="tender-123" />);

    expect(screen.getByTestId("tender-board-selector-loading")).toBeInTheDocument();
  });

  it("muestra CTA 'Crear tablero' cuando no hay columnas", async () => {
    useKanbanMock.mockReturnValue({
      columns: [],
      cards: [],
      loading: false,
      addCard: vi.fn(),
      moveCard: vi.fn(),
      archiveCard: vi.fn(),
    });
    const onNavigateToBoard = vi.fn();
    const user = userEvent.setup();

    render(
      <TenderBoardSelector
        tenderId="tender-123"
        onNavigateToBoard={onNavigateToBoard}
      />,
    );

    const cta = screen.getByRole("button", { name: /crear tablero/i });
    await user.click(cta);
    expect(onNavigateToBoard).toHaveBeenCalledTimes(1);
  });

  it("no en tablero: seleccionar columna llama addCard con los parámetros correctos", async () => {
    const addCard = vi.fn().mockResolvedValue(undefined);
    useKanbanMock.mockReturnValue({
      columns: [column({ id: "col1", name: "Por postular" }), column({ id: "col2", name: "En revisión", position: 1 })],
      cards: [], // la tarjeta no está en ninguna columna todavía
      tenders: {},
      loading: false,
      addCard,
      moveCard: vi.fn(),
      archiveCard: vi.fn(),
    });
    const user = userEvent.setup();

    render(<TenderBoardSelector tenderId="tender-123" />);

    // El dropdown debe mostrar la etiqueta "Agregar al tablero" cuando no está
    // en ninguna columna.
    const trigger = screen.getByRole("button", { name: /agregar al tablero/i });
    await user.click(trigger);
    await user.click(screen.getByRole("menuitem", { name: /en revisión/i }));

    await waitFor(() => {
      expect(addCard).toHaveBeenCalledWith(
        "tender-123",
        "col2",
        expect.anything(),
      );
    });
  });

  it("en tablero: cambiar columna llama moveCard; opción 'Quitar' llama archiveCard tras confirmación", async () => {
    const moveCard = vi.fn().mockResolvedValue(undefined);
    const archiveCard = vi.fn().mockResolvedValue(undefined);
    useKanbanMock.mockReturnValue({
      columns: [
        column({ id: "col1", name: "Por postular", card_count: 1 }),
        column({ id: "col2", name: "En revisión", position: 1, card_count: 2 }),
      ],
      cards: [card({ id: "card1", tender_id: "tender-123", column_id: "col1" })],
      tenders: {},
      loading: false,
      addCard: vi.fn(),
      moveCard,
      archiveCard,
    });
    const user = userEvent.setup();

    // La confirmación de "Quitar" usa `window.confirm`: lo mockeamos para
    // probar el camino afirmativo sin que el navegador abra el diálogo.
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);

    render(<TenderBoardSelector tenderId="tender-123" />);

    // Trigger muestra la columna actual.
    const trigger = screen.getByRole("button", { name: /por postular/i });
    await user.click(trigger);

    // Primera acción: cambiar a otra columna.
    await user.click(screen.getByRole("menuitem", { name: /en revisión/i }));
    await waitFor(() => {
      // moveCard usa tender_id como primer argumento (contrato real del hook).
      expect(moveCard).toHaveBeenCalledWith("tender-123", "col2", expect.any(Number));
    });

    // Volvemos a abrir y usamos "Quitar del tablero".
    await user.click(screen.getByRole("button"));
    await user.click(screen.getByRole("menuitem", { name: /quitar del tablero/i }));

    await waitFor(() => {
      expect(confirmSpy).toHaveBeenCalled();
      expect(archiveCard).toHaveBeenCalledWith("card1");
    });

    confirmSpy.mockRestore();
  });
});
