import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { UnbackedAspectsList } from "../UnbackedAspectsList";
import { InsufficientInfoBanner } from "../InsufficientInfoBanner";

describe("UnbackedAspectsList (CA3)", () => {
  it("renderiza la lista de aspectos que no constan en los documentos adjuntos", () => {
    const aspects = [
      "Presupuesto máximo disponible referencial",
      "Requisito de certificado ISO 9001",
    ];

    render(<UnbackedAspectsList aspects={aspects} />);

    expect(
      screen.getByText(/Aspectos no especificados en los documentos adjuntos:/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText("Presupuesto máximo disponible referencial")
    ).toBeInTheDocument();
    expect(
      screen.getByText("Requisito de certificado ISO 9001")
    ).toBeInTheDocument();
  });

  it("no renderiza nada si el arreglo de aspectos está vacío", () => {
    const { container } = render(<UnbackedAspectsList aspects={[]} />);
    expect(container.firstChild).toBeNull();
  });
});

describe("InsufficientInfoBanner (CA4)", () => {
  it("renderiza el banner de advertencia y sugerencia del foro de Mercado Público cuando hasSufficientInfo es false", () => {
    render(<InsufficientInfoBanner hasSufficientInfo={false} />);

    expect(
      screen.getByText(/Información no especificada en las bases/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /Se sugiere realizar la consulta formal mediante el Foro de Preguntas de Mercado Público/i
      )
    ).toBeInTheDocument();
  });

  it("no renderiza nada cuando hasSufficientInfo es true o undefined", () => {
    const { container: containerTrue } = render(
      <InsufficientInfoBanner hasSufficientInfo={true} />
    );
    expect(containerTrue.firstChild).toBeNull();

    const { container: containerUndefined } = render(
      <InsufficientInfoBanner hasSufficientInfo={undefined} />
    );
    expect(containerUndefined.firstChild).toBeNull();
  });
});
