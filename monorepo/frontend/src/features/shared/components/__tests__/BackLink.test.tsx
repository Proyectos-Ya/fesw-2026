import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BackLink } from "../BackLink";

const mockRouter = { push: vi.fn(), replace: vi.fn(), back: vi.fn() };

vi.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
}));

describe("BackLink", () => {
  const user = userEvent.setup();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("retrocede en el historial cuando hay de dónde volver", async () => {
    vi.spyOn(window.history, "length", "get").mockReturnValue(3);

    render(<BackLink fallbackHref="/matches">Volver</BackLink>);
    await user.click(screen.getByRole("button", { name: /volver/i }));

    expect(mockRouter.back).toHaveBeenCalledTimes(1);
    expect(mockRouter.push).not.toHaveBeenCalled();
  });

  it("usa el destino de respaldo si la pestaña no tiene historial", async () => {
    // Enlace abierto desde un correo: retroceder no haría nada y el usuario
    // quedaría encerrado en la ficha.
    vi.spyOn(window.history, "length", "get").mockReturnValue(1);

    render(<BackLink fallbackHref="/matches">Volver</BackLink>);
    await user.click(screen.getByRole("button", { name: /volver/i }));

    expect(mockRouter.push).toHaveBeenCalledWith("/matches");
    expect(mockRouter.back).not.toHaveBeenCalled();
  });
});
