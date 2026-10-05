import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { buildDigestCitation } from "../../test-utils";
import { DigestCitations } from "../DigestCitations";

describe("DigestCitations", () => {
  it("renderiza cita, documento, página y badge de verificada", () => {
    const cita = buildDigestCitation({
      documento: "Bases.pdf",
      pagina_u_hoja: "Pág 4",
      cita: "El plazo es de 30 días.",
      verificada: true,
    });

    render(<DigestCitations citas={[cita]} />);

    expect(screen.getByText("Ver cita")).toBeInTheDocument();
    expect(screen.getByText('"El plazo es de 30 días."')).toBeInTheDocument();
    expect(screen.getByText("Bases.pdf · Pág 4")).toBeInTheDocument();
    expect(screen.getByText("Cita verificada")).toBeInTheDocument();
  });

  it("renderiza badge sin verificar con título explicativo", () => {
    const cita = buildDigestCitation({
      documento: "Escaneado.pdf",
      pagina_u_hoja: null,
      cita: "Texto no indexado.",
      verificada: false,
    });

    render(<DigestCitations citas={[cita]} />);

    expect(screen.getByText("Sin verificar")).toBeInTheDocument();
  });

  it("muestra plural cuando hay múltiples citas", () => {
    const c1 = buildDigestCitation({ cita: "Cita 1" });
    const c2 = buildDigestCitation({ cita: "Cita 2" });

    render(<DigestCitations citas={[c1, c2]} />);

    expect(screen.getByText("Ver 2 citas")).toBeInTheDocument();
  });

  it("no renderiza nada si citas está vacío", () => {
    const { container } = render(<DigestCitations citas={[]} />);

    expect(container.firstChild).toBeNull();
  });
});
