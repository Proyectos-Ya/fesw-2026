import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DiscrepancyCard, type DiscrepancyView } from "../DiscrepancyCard";

describe("DiscrepancyCard (shared)", () => {
  const baseDiscrepancy: DiscrepancyView = {
    topic: "Cierre del primer llamado",
    description: "Mercado Público informa 04-10-2026 15:00, pero las bases señalan 05-10-2026 15:00.",
    conflicting_sources: [
      {
        document_name: "Bases.pdf",
        page_or_sheet: "Pág 3",
        quote: "El cierre será el 05-10-2026 a las 15:00.",
      },
    ],
  };

  it("renderiza con título personalizado si se provee", () => {
    render(
      <DiscrepancyCard
        discrepancy={baseDiscrepancy}
        title="Divergencia en fecha de cierre"
      />
    );

    expect(screen.getByText("Divergencia en fecha de cierre")).toBeInTheDocument();
  });

  it("renderiza con título por defecto si no se especifica", () => {
    render(<DiscrepancyCard discrepancy={baseDiscrepancy} />);

    expect(
      screen.getByText("Discrepancia detectada: Cierre del primer llamado")
    ).toBeInTheDocument();
  });

  it("renderiza dato de referencia si se provee", () => {
    render(
      <DiscrepancyCard
        discrepancy={baseDiscrepancy}
        reference={{ label: "Mercado Público informa", value: "04-10-2026 15:00" }}
      />
    );

    const ref = screen.getByTestId("discrepancy-reference");
    expect(ref).toBeInTheDocument();
    expect(ref).toHaveTextContent("Mercado Público informa: 04-10-2026 15:00");
  });

  it("no muestra reference cuando no se especifica", () => {
    render(<DiscrepancyCard discrepancy={baseDiscrepancy} />);

    expect(screen.queryByTestId("discrepancy-reference")).toBeNull();
  });
});
