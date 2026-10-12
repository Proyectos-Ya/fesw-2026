import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Toast } from "../Toast";

afterEach(() => {
  vi.useRealTimers();
});

describe("Toast", () => {
  it("muestra el mensaje como estado", () => {
    render(<Toast message="Respuesta guardada." onClose={vi.fn()} />);

    expect(screen.getByRole("status")).toHaveTextContent("Respuesta guardada.");
  });

  it("se cierra solo después del tiempo indicado", () => {
    vi.useFakeTimers();
    const onClose = vi.fn();
    render(<Toast message="Listo." onClose={onClose} durationMs={4000} />);

    act(() => vi.advanceTimersByTime(3999));
    expect(onClose).not.toHaveBeenCalled();
    act(() => vi.advanceTimersByTime(1));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("se puede cerrar a mano", async () => {
    const onClose = vi.fn();
    render(<Toast message="Listo." onClose={onClose} />);

    await userEvent.click(screen.getByRole("button", { name: "Cerrar aviso" }));

    expect(onClose).toHaveBeenCalled();
  });
});
