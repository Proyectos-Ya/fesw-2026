import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { HistoryPanel } from "../HistoryPanel";
import type { KanbanEvent } from "../../kanbanTypes";

const listEvents = vi.fn();
const restoreCard = vi.fn();

vi.mock("../../services/kanban.service", () => ({
  listEvents: (...args: unknown[]) => listEvents(...args),
  restoreCard: (...args: unknown[]) => restoreCard(...args),
}));

function event(overrides: Partial<KanbanEvent> = {}): KanbanEvent {
  return {
    id: "e1",
    supplier_id: "s1",
    user_id: "u1",
    user_name: "Ana",
    event_type: "card_added",
    tender_code: "1057539-228-COT26",
    entity_type: "card",
    entity_id: "c1",
    tender_id: "t1",
    tender_title: "Mantención de áreas verdes",
    details: {},
    created_at: "2026-02-01T12:00:00Z",
    ...overrides,
  };
}

describe("HistoryPanel", () => {
  beforeEach(() => {
    listEvents.mockReset();
    restoreCard.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("muestra los eventos cuando se abre", async () => {
    listEvents.mockResolvedValueOnce([event()]);
    render(<HistoryPanel open={true} onClose={() => undefined} />);

    expect(await screen.findByText("Mantención de áreas verdes", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("1057539-228-COT26")).toBeInTheDocument();
  });

  it("expone el botón 'Restaurar' solo para eventos card_archived", async () => {
    listEvents.mockResolvedValueOnce([
      event({ id: "e1", event_type: "card_archived", tender_title: "Lic archivada", entity_id: "c1" }),
      event({ id: "e2", event_type: "card_added", tender_title: "Lic añadida", entity_id: "c2" }),
    ]);
    render(<HistoryPanel open={true} onClose={() => undefined} />);

    await screen.findByText("Lic archivada", { exact: false });
    const buttons = screen.getAllByRole("button", { name: /restaurar/i });
    expect(buttons).toHaveLength(1);
  });

  it("llama a restoreCard cuando se hace click en 'Restaurar'", async () => {
    listEvents.mockResolvedValueOnce([
      event({ event_type: "card_archived", entity_id: "c1" }),
    ]);
    restoreCard.mockResolvedValueOnce({});
    const user = userEvent.setup();
    render(<HistoryPanel open={true} onClose={() => undefined} />);

    await screen.findByText("Mantención de áreas verdes", { exact: false });
    await user.click(screen.getByRole("button", { name: /restaurar/i }));

    await waitFor(() => {
      expect(restoreCard).toHaveBeenCalledWith("c1");
    });
  });

  it("muestra un mensaje cuando no hay actividad registrada", async () => {
    listEvents.mockResolvedValueOnce([]);
    render(<HistoryPanel open={true} onClose={() => undefined} />);

    expect(
      await screen.findByText(/todavía no hay actividad registrada/i),
    ).toBeInTheDocument();
  });
});
