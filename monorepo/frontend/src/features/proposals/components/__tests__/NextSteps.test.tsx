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

  it("pide el valor neto por ítem y el impuesto, y enlaza el cotizador de la página", () => {
    render(
      <NextSteps view={vista({ status: "READY", content: contenido() })} tenderCode="657-70-COT26" />,
    );

    const paso = screen.getByText(/valor unitario neto de cada ítem/);
    expect(paso).toHaveTextContent(/despacho/);
    expect(paso).toHaveTextContent(/exento, IVA, honorario o zona franca/);
    expect(screen.getByRole("link", { name: "cotizador" })).toHaveAttribute(
      "href",
      "#cotizacion",
    );
  });

  it("sin la ficha cargada no hay cotizador al que enlazar", () => {
    render(<NextSteps view={vista({ status: "READY", content: contenido() })} tenderCode={null} />);

    expect(screen.queryByRole("link", { name: "cotizador" })).not.toBeInTheDocument();
  });

  it("guía el detalle, la vigencia y la declaración jurada del formulario", () => {
    render(<NextSteps view={vista({ status: "READY", content: contenido() })} tenderCode={null} />);

    expect(screen.getByText(/detalle de la cotización/)).toBeInTheDocument();
    expect(screen.getByText(/fecha de vigencia/)).toBeInTheDocument();
    expect(screen.getByText(/Declaración Jurada de Habilidad/)).toHaveTextContent(
      /no se adjunta/i,
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
    expect(screen.getByText(/documento técnico en Word/)).toHaveTextContent(/20 MB/);
  });
});
