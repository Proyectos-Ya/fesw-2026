import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DiscrepancyCard } from "../DiscrepancyCard";
import type { DocumentDiscrepancy } from "../../types";

describe("DiscrepancyCard (CA2)", () => {
  it("renderiza el tema, descripción y las fuentes en conflicto de la discrepancia", () => {
    const mockDiscrepancy: DocumentDiscrepancy = {
      topic: "Plazo de entrega y ejecución",
      description:
        "Las Bases Administrativas señalan 30 días corridos mientras que las Especificaciones Técnicas indican 45 días corridos.",
      conflicting_sources: [
        {
          document_name: "Bases_Administrativas.pdf",
          page_or_sheet: "Página 5",
          quote: "El plazo de entrega es de 30 días corridos contados desde la OC.",
        },
        {
          document_name: "Especificaciones_Tecnicas.pdf",
          page_or_sheet: "Página 12",
          quote: "Plazo de ejecución técnica: 45 días corridos.",
        },
      ],
    };

    render(<DiscrepancyCard discrepancy={mockDiscrepancy} />);

    expect(
      screen.getByText(/Discrepancia detectada: Plazo de entrega y ejecución/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /Las Bases Administrativas señalan 30 días corridos mientras que las Especificaciones Técnicas indican 45 días corridos./i
      )
    ).toBeInTheDocument();

    expect(screen.getByText("Bases_Administrativas.pdf")).toBeInTheDocument();
    expect(screen.getByText("Página 5")).toBeInTheDocument();
    expect(
      screen.getByText(
        /"El plazo de entrega es de 30 días corridos contados desde la OC."/i
      )
    ).toBeInTheDocument();

    expect(screen.getByText("Especificaciones_Tecnicas.pdf")).toBeInTheDocument();
    expect(screen.getByText("Página 12")).toBeInTheDocument();
    expect(
      screen.getByText(/"Plazo de ejecución técnica: 45 días corridos."/i)
    ).toBeInTheDocument();
  });

  it("renderiza correctamente cuando no hay fuentes en conflicto explícitas", () => {
    const simpleDiscrepancy: DocumentDiscrepancy = {
      topic: "Garantía de seriedad",
      description: "Montos disímiles en los documentos adjuntos.",
      conflicting_sources: [],
    };

    render(<DiscrepancyCard discrepancy={simpleDiscrepancy} />);

    expect(
      screen.getByText(/Discrepancia detectada: Garantía de seriedad/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Montos disímiles en los documentos adjuntos./i)
    ).toBeInTheDocument();
  });
});
