import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { HighlightedText } from "../HighlightedText";
import { ProposalStepper } from "../ProposalStepper";

describe("ProposalStepper (CA6)", () => {
  it("en factibilidad marca el primer paso", () => {
    render(<ProposalStepper status="FEASIBILITY" stage={null} />);
    expect(screen.getByText("Factibilidad").closest("li")).toHaveAttribute(
      "aria-current",
      "step",
    );
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("mientras analiza dice en qué etapa está", () => {
    render(<ProposalStepper status={null} stage="analyzing" />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Analizando bases y experiencia",
    );
  });

  it("mientras redacta avanza al segundo paso", () => {
    render(<ProposalStepper status="FEASIBILITY" stage="drafting" />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Redactando nombre, descripción y documentos",
    );
    expect(screen.getByText("Redacción").closest("li")).toHaveAttribute(
      "aria-current",
      "step",
    );
  });

  it("con el borrador listo marca el tercer paso", () => {
    render(<ProposalStepper status="READY" stage={null} />);
    expect(screen.getByText("Borrador").closest("li")).toHaveAttribute(
      "aria-current",
      "step",
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
