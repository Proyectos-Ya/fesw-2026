import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { KeywordSuggestions } from "../KeywordSuggestions";

const SUGGESTIONS = ["pintura", "revestimiento", "servicio técnico"];

describe("KeywordSuggestions", () => {
  it("agrega una palabra clave al hacer clic en su chip", () => {
    const onAdd = vi.fn();
    render(<KeywordSuggestions suggestions={SUGGESTIONS} selected={[]} onAdd={onAdd} />);

    fireEvent.click(screen.getByRole("button", { name: "Agregar revestimiento" }));

    expect(onAdd).toHaveBeenCalledWith(["revestimiento"]);
  });

  it("agrega todas las que faltan de una vez", () => {
    const onAdd = vi.fn();
    render(
      <KeywordSuggestions suggestions={SUGGESTIONS} selected={["pintura"]} onAdd={onAdd} />,
    );

    fireEvent.click(screen.getByRole("button", { name: /agregar todas/i }));

    expect(onAdd).toHaveBeenCalledWith(["revestimiento", "servicio técnico"]);
  });

  it("no vuelve a sugerir las que el usuario ya tiene, sin importar mayúsculas", () => {
    render(
      <KeywordSuggestions suggestions={SUGGESTIONS} selected={["Pintura"]} onAdd={vi.fn()} />,
    );

    expect(screen.queryByRole("button", { name: "Agregar pintura" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Agregar revestimiento" })).toBeInTheDocument();
  });

  it("desaparece cuando ya no quedan sugerencias", () => {
    const { container } = render(
      <KeywordSuggestions suggestions={SUGGESTIONS} selected={SUGGESTIONS} onAdd={vi.fn()} />,
    );

    expect(container).toBeEmptyDOMElement();
  });
});
