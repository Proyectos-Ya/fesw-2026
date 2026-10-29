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

  it("descarta una palabra clave con su botón de descarte", () => {
    const onDismiss = vi.fn();
    render(
      <KeywordSuggestions
        suggestions={SUGGESTIONS}
        selected={[]}
        onAdd={vi.fn()}
        onDismiss={onDismiss}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Descartar revestimiento" }));

    expect(onDismiss).toHaveBeenCalledWith("revestimiento");
  });

  it("descartar no agrega la palabra", () => {
    const onAdd = vi.fn();
    render(
      <KeywordSuggestions
        suggestions={SUGGESTIONS}
        selected={[]}
        onAdd={onAdd}
        onDismiss={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Descartar pintura" }));

    expect(onAdd).not.toHaveBeenCalled();
  });

  it("no muestra las descartadas, sin importar mayúsculas ni espacios", () => {
    render(
      <KeywordSuggestions
        suggestions={SUGGESTIONS}
        selected={[]}
        dismissed={[" Pintura "]}
        onAdd={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );

    expect(screen.queryByRole("button", { name: "Agregar pintura" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Descartar pintura" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Agregar revestimiento" })).toBeInTheDocument();
  });

  it("agregar todas omite las descartadas", () => {
    const onAdd = vi.fn();
    render(
      <KeywordSuggestions
        suggestions={SUGGESTIONS}
        selected={[]}
        dismissed={["revestimiento"]}
        onAdd={onAdd}
        onDismiss={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /agregar todas/i }));

    expect(onAdd).toHaveBeenCalledWith(["pintura", "servicio técnico"]);
  });

  it("desaparece cuando todas están descartadas", () => {
    const { container } = render(
      <KeywordSuggestions
        suggestions={SUGGESTIONS}
        selected={[]}
        dismissed={SUGGESTIONS}
        onAdd={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("sin onDismiss no muestra botones de descarte", () => {
    render(<KeywordSuggestions suggestions={SUGGESTIONS} selected={[]} onAdd={vi.fn()} />);

    expect(screen.queryByRole("button", { name: /^Descartar/ })).not.toBeInTheDocument();
  });
});
