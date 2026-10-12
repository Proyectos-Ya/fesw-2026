import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { HighlightedText } from "../HighlightedText";
import { StageNotice } from "../StageNotice";

describe("StageNotice (CA6)", () => {
  it("sin etapa en curso no muestra nada", () => {
    const { container } = render(<StageNotice stage={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("mientras analiza dice en qué etapa está", () => {
    render(<StageNotice stage="analyzing" />);
    expect(screen.getByRole("status")).toHaveTextContent("Analizando bases y experiencia");
  });

  it("mientras redacta dice en qué etapa está", () => {
    render(<StageNotice stage="drafting" />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Redactando nombre, descripción y documentos",
    );
  });

  it("mientras regenera dice que usa las instrucciones", () => {
    render(<StageNotice stage="regenerating" />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Regenerando el borrador con tus instrucciones",
    );
  });
});

describe("HighlightedText (CA2)", () => {
  it("resalta los vacíos", () => {
    render(
      <p>
        <HighlightedText text="Relator: (Por favor, inserte aquí el valor nombre del relator)." />
      </p>,
    );
    expect(
      screen.getByText("(Por favor, inserte aquí el valor nombre del relator)").tagName,
    ).toBe("MARK");
  });
});
