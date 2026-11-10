import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PostularEnMercadoPublicoButton } from "../PostularEnMercadoPublicoButton";

describe("PostularEnMercadoPublicoButton (CA1)", () => {
  it("muestra el botón 'Postular en Mercado Público' habilitado cuando canWrite y no está expirada", () => {
    const onClickMock = vi.fn();
    render(
      <PostularEnMercadoPublicoButton
        canWrite={true}
        isExpired={false}
        busy={false}
        onClick={onClickMock}
      />
    );

    const btn = screen.getByRole("button", { name: /Postular en Mercado Público/i });
    expect(btn).toBeInTheDocument();
    expect(btn).not.toBeDisabled();

    fireEvent.click(btn);
    expect(onClickMock).toHaveBeenCalled();
  });

  it("deshabilita el botón con explicación si la licitación cerró", () => {
    render(
      <PostularEnMercadoPublicoButton
        canWrite={true}
        isExpired={true}
        busy={false}
        onClick={vi.fn()}
      />
    );

    const btn = screen.getByRole("button", { name: /Postular en Mercado Público/i });
    expect(btn).toBeDisabled();
    expect(screen.getByText(/La licitación ya cerró/i)).toBeInTheDocument();
  });

  it("deshabilita el botón si el usuario no tiene permisos de edición", () => {
    render(
      <PostularEnMercadoPublicoButton
        canWrite={false}
        isExpired={false}
        busy={false}
        onClick={vi.fn()}
      />
    );

    const btn = screen.getByRole("button", { name: /Postular en Mercado Público/i });
    expect(btn).toBeDisabled();
    expect(screen.getByText(/Tu rol no permite postular/i)).toBeInTheDocument();
  });
});
