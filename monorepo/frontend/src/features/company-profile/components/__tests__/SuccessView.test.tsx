import React from "react";
import { render, screen, act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SuccessView } from "../SuccessView";

describe("SuccessView", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("muestra el título y el subtítulo de redirección", () => {
    render(<SuccessView onRedirect={vi.fn()} />);

    expect(screen.getByText("¡Perfil creado con éxito!")).toBeInTheDocument();
    expect(screen.getByText(/Redirigiendo a tu dashboard/)).toBeInTheDocument();
  });

  it("llama a onRedirect después de 2500 ms", () => {
    const onRedirect = vi.fn();
    render(<SuccessView onRedirect={onRedirect} />);

    expect(onRedirect).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(2500);
    });

    expect(onRedirect).toHaveBeenCalledOnce();
  });

  it("no llama a onRedirect antes de que pasen 2500 ms", () => {
    const onRedirect = vi.fn();
    render(<SuccessView onRedirect={onRedirect} />);

    act(() => {
      vi.advanceTimersByTime(2499);
    });

    expect(onRedirect).not.toHaveBeenCalled();
  });
});
