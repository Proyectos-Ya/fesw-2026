import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SearchBar } from "../SearchBar";

describe("SearchBar", () => {
  it("renderiza el input con el valor y placeholder", () => {
    render(<SearchBar value="equipamiento" onChange={vi.fn()} />);

    // type="text" y no "search": la X nativa del navegador duplicaba el botón de limpiar (#209).
    const input = screen.getByRole("textbox", { name: /buscar licitaciones/i });
    expect(input).toHaveValue("equipamiento");
  });

  it("llama a onChange cuando el usuario escribe", () => {
    const handleChange = vi.fn();
    render(<SearchBar value="" onChange={handleChange} />);

    // type="text" y no "search": la X nativa del navegador duplicaba el botón de limpiar (#209).
    const input = screen.getByRole("textbox", { name: /buscar licitaciones/i });
    fireEvent.change(input, { target: { value: "computadores" } });

    expect(handleChange).toHaveBeenCalledWith("computadores");
  });

  it("muestra el botón de limpiar cuando hay texto y al hacer click lo limpia", () => {
    const handleChange = vi.fn();
    render(<SearchBar value="limpieza" onChange={handleChange} />);

    const clearButton = screen.getByRole("button", { name: /limpiar búsqueda/i });
    expect(clearButton).toBeInTheDocument();

    fireEvent.click(clearButton);
    expect(handleChange).toHaveBeenCalledWith("");
  });
});
