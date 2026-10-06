import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { NextSteps } from "../NextSteps";
import { vista } from "../../testing/fixtures";
import type { DraftContent } from "../../types";

const contenido = (overrides: Partial<DraftContent> = {}): DraftContent => ({
  offer_name: { paragraphs: [{ text: "Oferta", sources: [], placeholders: [] }] },
  offer_description: { paragraphs: [] },
  required_documents: {
    paragraphs: [{ text: "Adjuntar cotización", sources: [], placeholders: [] }],
  },
  technical_document: null,
  ...overrides,
});

describe("NextSteps", () => {
  it("enlaza la ficha oficial de la Compra Ágil", () => {
    render(<NextSteps view={vista({ status: "READY", content: contenido() })} tenderCode="657-70-COT26" />);

    expect(screen.getByRole("link", { name: /657-70-COT26/ })).toHaveAttribute(
      "href",
      "https://buscador.mercadopublico.cl/ficha?code=657-70-COT26",
    );
  });

  it("si piden cotización enlaza el cotizador de la misma página", () => {
    render(<NextSteps view={vista({ status: "READY", content: contenido() })} tenderCode={null} />);

    expect(screen.getByRole("link", { name: "cotizador" })).toHaveAttribute(
      "href",
      "#cotizacion",
    );
  });

  it("menciona el documento técnico solo si existe", () => {
    const { rerender } = render(
      <NextSteps view={vista({ status: "READY", content: contenido() })} tenderCode={null} />,
    );
    expect(screen.queryByText(/documento técnico/)).not.toBeInTheDocument();

    rerender(
      <NextSteps
        view={vista({
          status: "READY",
          content: contenido({ technical_document: { sections: [] } }),
        })}
        tenderCode={null}
      />,
    );
    expect(screen.getByText(/documento técnico en Word/)).toBeInTheDocument();
  });
});
