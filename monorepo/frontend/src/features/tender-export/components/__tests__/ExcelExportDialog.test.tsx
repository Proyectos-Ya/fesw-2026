import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ExcelExportDialog } from "../ExcelExportDialog";

function abrir() {
  const onConfirm = vi.fn();
  const onClose = vi.fn();
  render(<ExcelExportDialog open onConfirm={onConfirm} onClose={onClose} />);
  return { onConfirm, onClose };
}

describe("ExcelExportDialog", () => {
  it("parte con todas las secciones marcadas", () => {
    abrir();

    const secciones = screen.getAllByRole("switch");
    expect(secciones).toHaveLength(5);
    secciones.forEach((s) => expect(s).toBeChecked());
  });

  it("genera con las secciones que siguen marcadas, en su orden", async () => {
    // Criterio 5: p. ej. omitir el análisis de la IA.
    const user = userEvent.setup();
    const { onConfirm } = abrir();

    await user.click(screen.getByRole("switch", { name: /análisis de la ia/i }));
    await user.click(screen.getByRole("button", { name: /generar excel/i }));

    expect(onConfirm).toHaveBeenCalledWith(["datos_generales", "montos", "items", "hitos"]);
  });

  it("puede dejar solo las fechas clave", async () => {
    const user = userEvent.setup();
    const { onConfirm } = abrir();

    for (const nombre of [/datos generales/i, /montos/i, /datos técnicos/i, /análisis/i]) {
      await user.click(screen.getByRole("switch", { name: nombre }));
    }
    await user.click(screen.getByRole("button", { name: /generar excel/i }));

    expect(onConfirm).toHaveBeenCalledWith(["hitos"]);
  });

  it("sin ninguna sección no deja generar y lo explica", async () => {
    const user = userEvent.setup();
    abrir();

    for (const seccion of screen.getAllByRole("switch")) await user.click(seccion);

    expect(screen.getByRole("button", { name: /generar excel/i })).toBeDisabled();
    expect(screen.getByText(/elige al menos una sección/i)).toBeInTheDocument();
  });

  it("se cierra con Cancelar y con Escape", async () => {
    const user = userEvent.setup();
    const { onClose, onConfirm } = abrir();

    await user.click(screen.getByRole("button", { name: /cancelar/i }));
    await user.keyboard("{Escape}");

    expect(onClose).toHaveBeenCalledTimes(2);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("cerrado no muestra nada", () => {
    render(<ExcelExportDialog open={false} onConfirm={vi.fn()} onClose={vi.fn()} />);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
