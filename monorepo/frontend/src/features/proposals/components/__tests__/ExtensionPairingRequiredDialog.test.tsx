import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ExtensionPairingRequiredDialog } from "../ExtensionPairingRequiredDialog";

describe("ExtensionPairingRequiredDialog", () => {
  const setup = (over: Partial<Parameters<typeof ExtensionPairingRequiredDialog>[0]> = {}) => {
    const props = {
      open: true,
      busy: false,
      error: null,
      onPair: vi.fn(),
      onRetry: vi.fn(),
      onPostManually: vi.fn(),
      onClose: vi.fn(),
      ...over,
    };
    render(<ExtensionPairingRequiredDialog {...props} />);
    return props;
  };

  it("explica que falta vincular y ofrece Vincular, Reintentar y Postular manualmente", () => {
    const props = setup();
    expect(screen.getByText(/no está vinculada/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Vincular" }));
    fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    fireEvent.click(screen.getByRole("button", { name: /Postular manualmente/i }));
    expect(props.onPair).toHaveBeenCalledTimes(1);
    expect(props.onRetry).toHaveBeenCalledTimes(1);
    expect(props.onPostManually).toHaveBeenCalledTimes(1);
  });

  it("muestra el error y deshabilita las acciones mientras trabaja", () => {
    setup({ busy: true, error: "La extensión no confirmó la vinculación." });
    expect(screen.getByText("La extensión no confirmó la vinculación.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Vincular" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeDisabled();
  });

  it("no renderiza nada cerrado", () => {
    setup({ open: false });
    expect(screen.queryByText(/no está vinculada/i)).not.toBeInTheDocument();
  });
});
