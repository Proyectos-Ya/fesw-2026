import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DefaultTimeDialog } from "../DefaultTimeDialog";

describe("DefaultTimeDialog", () => {
  it("propone las 09:00 como inicio de jornada", () => {
    render(<DefaultTimeDialog open count={2} onConfirm={vi.fn()} onCancel={vi.fn()} />);

    expect(screen.getByRole("dialog", { name: /confirma una hora/i })).toBeInTheDocument();
    expect(screen.getByText(/2 hitos no tienen hora exacta/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/hora para los hitos sin hora/i)).toHaveValue("09:00");
  });

  it("confirma con la hora elegida", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(<DefaultTimeDialog open count={1} onConfirm={onConfirm} onCancel={vi.fn()} />);

    const hora = screen.getByLabelText(/hora para los hitos sin hora/i);
    await user.clear(hora);
    await user.type(hora, "14:30");
    await user.click(screen.getByRole("button", { name: /confirmar y sincronizar/i }));

    expect(onConfirm).toHaveBeenCalledWith("14:30");
  });

  it("habla en singular con un solo hito", () => {
    render(<DefaultTimeDialog open count={1} onConfirm={vi.fn()} onCancel={vi.fn()} />);

    expect(screen.getByText(/1 hito no tiene hora exacta/i)).toBeInTheDocument();
  });

  it("no permite confirmar sin hora", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(<DefaultTimeDialog open count={1} onConfirm={onConfirm} onCancel={vi.fn()} />);

    await user.clear(screen.getByLabelText(/hora para los hitos sin hora/i));

    expect(screen.getByRole("button", { name: /confirmar y sincronizar/i })).toBeDisabled();
  });

  it("cancelar no sincroniza", async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    const onConfirm = vi.fn();
    render(<DefaultTimeDialog open count={1} onConfirm={onConfirm} onCancel={onCancel} />);

    await user.click(screen.getByRole("button", { name: "Cancelar" }));

    expect(onCancel).toHaveBeenCalled();
    expect(onConfirm).not.toHaveBeenCalled();
  });
});
