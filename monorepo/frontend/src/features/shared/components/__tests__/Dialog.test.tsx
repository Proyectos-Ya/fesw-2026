import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Dialog } from "../Dialog";

function renderDialog(open: boolean, onClose = vi.fn(), preventOutsideClose = false) {
  render(
    <>
      <button type="button">Afuera</button>
      <Dialog
        open={open}
        title="Confirmar hora"
        onClose={onClose}
        preventOutsideClose={preventOutsideClose}
      >
        <input aria-label="Hora" />
        <button type="button">Aceptar</button>
      </Dialog>
    </>,
  );
  return onClose;
}

describe("Dialog", () => {
  it("cerrado no renderiza nada", () => {
    renderDialog(false);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("es un diálogo modal con nombre accesible", () => {
    renderDialog(true);

    const dialogo = screen.getByRole("dialog", { name: "Confirmar hora" });
    expect(dialogo).toHaveAttribute("aria-modal", "true");
  });

  it("lleva el foco al primer control al abrir", () => {
    renderDialog(true);

    expect(screen.getByLabelText("Hora")).toHaveFocus();
  });

  it("Escape lo cierra", async () => {
    const user = userEvent.setup();
    const onClose = renderDialog(true);

    await user.keyboard("{Escape}");

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("Tab no saca el foco del diálogo", async () => {
    const user = userEvent.setup();
    renderDialog(true);

    await user.tab();
    expect(screen.getByRole("button", { name: "Aceptar" })).toHaveFocus();
    await user.tab();
    expect(screen.getByLabelText("Hora")).toHaveFocus();
  });

  it("con preventOutsideClose=true no se cierra al presionar Escape", async () => {
    const user = userEvent.setup();
    const onClose = renderDialog(true, vi.fn(), true);

    await user.keyboard("{Escape}");

    expect(onClose).not.toHaveBeenCalled();
  });

  it("con preventOutsideClose=true no se cierra al hacer clic en el backdrop", async () => {
    const user = userEvent.setup();
    const onClose = renderDialog(true, vi.fn(), true);

    const dialog = screen.getByRole("dialog");
    const backdrop = dialog.parentElement;
    expect(backdrop).not.toBeNull();
    if (backdrop) {
      await user.click(backdrop);
    }

    expect(onClose).not.toHaveBeenCalled();
  });
});
