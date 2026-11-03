import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { buildTenderMapPoint } from "../../test-utils";
import { TenderMapSummary } from "../TenderMapSummary";

describe("TenderMapSummary", () => {
  it("muestra nombre, organismo, dirección de entrega y cierre", () => {
    render(<TenderMapSummary point={buildTenderMapPoint()} />);

    expect(screen.getByText("Insumos de aseo")).toBeInTheDocument();
    expect(screen.getByText("Municipalidad de Ancud")).toBeInTheDocument();
    expect(screen.getByText("Yerbas Buenas #915")).toBeInTheDocument();
    // 18:00 UTC es 15:00 en Santiago, el mismo día.
    expect(screen.getByText(/3 nov 2026/)).toBeInTheDocument();
  });

  it("enlaza al detalle de la licitación", () => {
    render(<TenderMapSummary point={buildTenderMapPoint({ id: "abc-123" })} />);

    expect(screen.getByRole("link", { name: /ver detalle/i })).toHaveAttribute(
      "href",
      "/matches/abc-123",
    );
  });

  it("avisa cuando el punto es aproximado", () => {
    render(<TenderMapSummary point={buildTenderMapPoint({ precision: "comuna" })} />);

    expect(screen.getByText(/ubicación aproximada/i)).toBeInTheDocument();
  });

  it("con la dirección encontrada no avisa nada", () => {
    render(<TenderMapSummary point={buildTenderMapPoint()} />);

    expect(screen.queryByText(/ubicación aproximada/i)).not.toBeInTheDocument();
  });

  it("sin organismo lo dice en vez de dejarlo vacío", () => {
    render(<TenderMapSummary point={buildTenderMapPoint({ buyer_name: null })} />);

    expect(screen.getByText("Organismo no informado")).toBeInTheDocument();
  });
});
