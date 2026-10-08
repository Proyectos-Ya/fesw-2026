import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { HistoryPanel } from "../HistoryPanel";
import type { KanbanArchiveEntry } from "../../kanbanTypes";

const listArchive = vi.fn();
const restoreCard = vi.fn();

vi.mock("../../services/kanban.service", () => ({
  listArchive: (...args: unknown[]) => listArchive(...args),
  restoreCard: (...args: unknown[]) => restoreCard(...args),
}));

function entry(overrides: Partial<KanbanArchiveEntry> = {}): KanbanArchiveEntry {
  return {
    id: "c1",
    tender_id: "t1",
    tender_title: "Mantención de áreas verdes",
    tender_external_id: "1057539-228-COT26",
    column_id: "col1",
    column_name: "En revisión",
    board_entered_at: "2026-01-01T12:00:00Z",
    archived_at: "2026-02-01T12:00:00Z",
    archived_reason: "manual",
    ...overrides,
  };
}

describe("HistoryPanel", () => {
  beforeEach(() => {
    listArchive.mockReset();
    restoreCard.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("muestra las entradas archivadas cuando se abre", async () => {
    listArchive.mockResolvedValueOnce([entry()]);
    render(<HistoryPanel open={true} onClose={() => undefined} />);

    expect(await screen.findByText("Mantención de áreas verdes")).toBeInTheDocument();
    expect(screen.getByText("En revisión")).toBeInTheDocument();
    expect(screen.getByText("Manual")).toBeInTheDocument();
  });

  it("expone el botón 'Restaurar' solo para entradas manuales", async () => {
    listArchive.mockResolvedValueOnce([
      entry({ id: "a", archived_reason: "manual", tender_title: "Lic manual" }),
      entry({
        id: "b",
        archived_reason: "auto_3m",
        tender_title: "Lic auto",
        tender_external_id: "AUTO-1",
      }),
    ]);
    render(<HistoryPanel open={true} onClose={() => undefined} />);

    await screen.findByText("Lic manual");
    const buttons = screen.getAllByRole("button", { name: /restaurar/i });
    // Solo la manual expone el botón "Restaurar"; la auto no debe aparecer.
    expect(buttons).toHaveLength(1);
  });

  it("llama a restoreCard cuando se hace click en 'Restaurar'", async () => {
    listArchive.mockResolvedValueOnce([entry()]);
    restoreCard.mockResolvedValueOnce({});
    const user = userEvent.setup();
    render(<HistoryPanel open={true} onClose={() => undefined} />);

    await screen.findByText("Mantención de áreas verdes");
    await user.click(screen.getByRole("button", { name: /restaurar/i }));

    await waitFor(() => {
      expect(restoreCard).toHaveBeenCalledWith("c1");
    });
  });

  it("muestra un mensaje cuando no hay historial", async () => {
    listArchive.mockResolvedValueOnce([]);
    render(<HistoryPanel open={true} onClose={() => undefined} />);

    expect(
      await screen.findByText(/todavía no hay tarjetas archivadas/i),
    ).toBeInTheDocument();
  });
});
