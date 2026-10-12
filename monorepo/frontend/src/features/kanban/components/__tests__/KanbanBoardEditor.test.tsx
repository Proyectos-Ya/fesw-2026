import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import {
  KanbanBoardEditor,
  _computeReorderedIds,
} from "../KanbanBoardEditor";
import type { KanbanColumn } from "../../kanbanTypes";
import { PALETTE } from "../../constants";

function makeColumn(partial: Partial<KanbanColumn> & { id: string }): KanbanColumn {
  return {
    id: partial.id,
    name: partial.name ?? `Columna ${partial.id}`,
    position: partial.position ?? 0,
    color: partial.color ?? PALETTE[0],
    card_count: partial.card_count ?? 0,
    created_at: partial.created_at ?? "2026-01-01T00:00:00Z",
  };
}

function renderEditor(overrides: Partial<Parameters<typeof KanbanBoardEditor>[0]> = {}) {
  const columns = overrides.columns ?? [
    makeColumn({ id: "a", name: "Por revisar", position: 0 }),
    makeColumn({ id: "b", name: "En revisión", position: 1 }),
    makeColumn({ id: "c", name: "Postulando", position: 2 }),
  ];
  const props = {
    open: true,
    columns,
    onClose: vi.fn(),
    onRename: vi.fn(),
    onRecolor: vi.fn(),
    onDelete: vi.fn(),
    onAddColumn: vi.fn(),
    onReorder: vi.fn(),
    ...overrides,
  };
  const utils = render(<KanbanBoardEditor {...props} />);
  return { ...utils, props };
}

describe("KanbanBoardEditor", () => {
  it("no renderiza nada cuando open es false", () => {
    renderEditor({ open: false });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("abre el modal con el título 'Editar tablero' y lista las columnas", () => {
    renderEditor();
    expect(screen.getByRole("dialog", { name: /editar tablero/i })).toBeInTheDocument();
    expect(screen.getByDisplayValue("Por revisar")).toBeInTheDocument();
    expect(screen.getByDisplayValue("En revisión")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Postulando")).toBeInTheDocument();
  });

  it("cerrar llama a onClose", async () => {
    const user = userEvent.setup();
    const { props } = renderEditor();
    await user.click(screen.getByRole("button", { name: /^cerrar$/i }));
    expect(props.onClose).toHaveBeenCalled();
  });

  it("renombrar una columna llama a onRename con el nuevo nombre", async () => {
    const user = userEvent.setup();
    const { props } = renderEditor();
    const input = screen.getByDisplayValue("Por revisar");
    await user.clear(input);
    await user.type(input, "Pendientes");
    await user.tab(); // blur commits
    expect(props.onRename).toHaveBeenCalledWith("a", "Pendientes");
  });

  it("cambiar el color llama a onRecolor con el hex seleccionado", async () => {
    const user = userEvent.setup();
    const { props } = renderEditor();
    // Botón de color de la primera fila: hay varios de cada color (uno por fila).
    // Tomamos el primero del segundo color (índice 1) de la primera fila.
    const colorButtons = screen.getAllByLabelText(`Color ${PALETTE[1]}`);
    await user.click(colorButtons[0]);
    expect(props.onRecolor).toHaveBeenCalledWith("a", PALETTE[1]);
  });

  it("click en 'Agregar columna' llama a onAddColumn con nombre por defecto", async () => {
    const user = userEvent.setup();
    const { props } = renderEditor();
    await user.click(screen.getByRole("button", { name: /agregar columna/i }));
    expect(props.onAddColumn).toHaveBeenCalledWith("Nueva columna");
  });

  it("eliminar una columna SIN tarjetas llama a onDelete directo", async () => {
    const user = userEvent.setup();
    const { props } = renderEditor();
    await user.click(screen.getByRole("button", { name: /eliminar columna por revisar/i }));
    expect(props.onDelete).toHaveBeenCalledWith("a");
  });

  it("eliminar una columna CON tarjetas pide confirmación antes de borrar", async () => {
    const user = userEvent.setup();
    const columns = [
      makeColumn({ id: "a", name: "Por revisar", position: 0, card_count: 3 }),
      makeColumn({ id: "b", name: "En revisión", position: 1 }),
    ];
    const { props } = renderEditor({ columns });

    await user.click(screen.getByRole("button", { name: /eliminar columna por revisar/i }));
    expect(props.onDelete).not.toHaveBeenCalled();
    expect(screen.getByText(/tiene 3 tarjetas/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /^eliminar$/i }));
    expect(props.onDelete).toHaveBeenCalledWith("a");
  });

  it("cancelar la confirmación de eliminación no borra", async () => {
    const user = userEvent.setup();
    const columns = [
      makeColumn({ id: "a", name: "Por revisar", position: 0, card_count: 2 }),
    ];
    const { props } = renderEditor({ columns });

    await user.click(screen.getByRole("button", { name: /eliminar columna por revisar/i }));
    await user.click(screen.getByRole("button", { name: /^cancelar$/i }));
    expect(props.onDelete).not.toHaveBeenCalled();
  });
});

describe("_computeReorderedIds (handler de drag end)", () => {
  const columns = [
    makeColumn({ id: "a", position: 0 }),
    makeColumn({ id: "b", position: 1 }),
    makeColumn({ id: "c", position: 2 }),
    makeColumn({ id: "d", position: 3 }),
  ];

  it("reordena cuando el activo cae encima de otro", () => {
    // Mover 'a' hasta la posición de 'c' → ['b','c','a','d']
    expect(_computeReorderedIds(columns, "a", "c")).toEqual(["b", "c", "a", "d"]);
  });

  it("devuelve null cuando activo == over", () => {
    expect(_computeReorderedIds(columns, "b", "b")).toBeNull();
  });

  it("devuelve null si alguna id no existe", () => {
    expect(_computeReorderedIds(columns, "zzz", "a")).toBeNull();
  });
});
