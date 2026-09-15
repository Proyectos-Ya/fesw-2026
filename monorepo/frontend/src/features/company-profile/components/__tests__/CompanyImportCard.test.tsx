import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CompanyImportCard } from "../CompanyImportCard";
import { ApiError } from "@/features/shared/api/client";
import type { CompanyProfileImport } from "../../services/supplierService";

const importCompanyProfileMock = vi.fn();

vi.mock("../../services/supplierService", () => ({
  importCompanyProfile: (rut: string) =>
    importCompanyProfileMock(rut) as Promise<CompanyProfileImport>,
}));

const IMPORTED: CompanyProfileImport = {
  source: "sre",
  rut: "76668304-5",
  legal_name: "Planeta Libre Soluciones Sustentables Limitada",
  is_active: null,
  regions: [],
  sectors: ["Obras de Construcción e Infraestructura"],
  keywords: ["pintura"],
  notices: ["La fuente consultada no informa la dirección de tu empresa."],
};

afterEach(() => {
  vi.clearAllMocks();
});

describe("CompanyImportCard", () => {
  it("no importa nada hasta que el usuario aprieta el botón", () => {
    render(<CompanyImportCard rut="76.668.304-5" imported={null} onImported={vi.fn()} />);

    expect(screen.getByText(/76\.668\.304-5/)).toBeInTheDocument();
    expect(importCompanyProfileMock).not.toHaveBeenCalled();
  });

  it("importa con el RUT del paso anterior y entrega el resultado", async () => {
    importCompanyProfileMock.mockResolvedValue(IMPORTED);
    const onImported = vi.fn();
    render(<CompanyImportCard rut="76.668.304-5" imported={null} onImported={onImported} />);

    fireEvent.click(screen.getByRole("button", { name: /importar datos/i }));

    await vi.waitFor(() => expect(onImported).toHaveBeenCalledWith(IMPORTED));
    expect(importCompanyProfileMock).toHaveBeenCalledWith("76.668.304-5");
  });

  it("muestra la fuente, la empresa encontrada y los avisos tras importar", () => {
    render(<CompanyImportCard rut="76.668.304-5" imported={IMPORTED} onImported={vi.fn()} />);

    expect(screen.getByText(/importados desde SRE/i)).toBeInTheDocument();
    expect(screen.getByText(/Planeta Libre Soluciones Sustentables Limitada/)).toBeInTheDocument();
    expect(screen.getByText(IMPORTED.notices[0])).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /volver a importar/i })).toBeInTheDocument();
  });

  it("muestra el mensaje del backend cuando no hay datos para el RUT", async () => {
    importCompanyProfileMock.mockRejectedValue(
      new ApiError(404, "No encontramos datos para el RUT 76668304-5."),
    );
    const onImported = vi.fn();
    render(<CompanyImportCard rut="76.668.304-5" imported={null} onImported={onImported} />);

    fireEvent.click(screen.getByRole("button", { name: /importar datos/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No encontramos datos para el RUT 76668304-5.",
    );
    expect(onImported).not.toHaveBeenCalled();
  });

  it("muestra un mensaje genérico cuando falla la red", async () => {
    importCompanyProfileMock.mockRejectedValue(new TypeError("Failed to fetch"));
    render(<CompanyImportCard rut="76.668.304-5" imported={null} onImported={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: /importar datos/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/no pudimos importar/i);
  });
});
