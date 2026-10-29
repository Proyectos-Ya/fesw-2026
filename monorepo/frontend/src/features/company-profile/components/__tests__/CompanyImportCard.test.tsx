import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CompanyImportCard } from "../CompanyImportCard";
import { ApiError, TimeoutError } from "@/features/shared/api/client";
import type { CompanyProfileImport } from "../../services/supplierService";

const importCompanyProfileMock = vi.fn();

vi.mock("../../services/supplierService", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../services/supplierService")>()),
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
    render(<CompanyImportCard rut="76.668.304-5" imported={null} onImported={vi.fn()} onInvalidRut={vi.fn()} />);

    expect(screen.getByText(/importa los datos de tu empresa/i)).toBeInTheDocument();
    expect(importCompanyProfileMock).not.toHaveBeenCalled();
  });

  it("importa con el RUT del paso anterior y entrega el resultado", async () => {
    importCompanyProfileMock.mockResolvedValue(IMPORTED);
    const onImported = vi.fn();
    render(<CompanyImportCard rut="76.668.304-5" imported={null} onImported={onImported} onInvalidRut={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: /importar datos/i }));

    await vi.waitFor(() => expect(onImported).toHaveBeenCalledWith(IMPORTED));
    expect(importCompanyProfileMock).toHaveBeenCalledWith("76.668.304-5");
  });

  it("muestra la fuente, la empresa encontrada y los avisos tras importar", () => {
    render(<CompanyImportCard rut="76.668.304-5" imported={IMPORTED} onImported={vi.fn()} onInvalidRut={vi.fn()} />);

    expect(screen.getByText(/importados desde SRE/i)).toBeInTheDocument();
    expect(screen.getByText(/Planeta Libre Soluciones Sustentables Limitada/)).toBeInTheDocument();
    expect(screen.getByText(IMPORTED.notices[0])).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /volver a importar/i })).toBeInTheDocument();
  });

  it("muestra ChileRUT Empresa como nombre legible de la fuente chilerut", () => {
    render(
      <CompanyImportCard
        rut="76.668.304-5"
        imported={{ ...IMPORTED, source: "chilerut" }}
        onImported={vi.fn()}
        onInvalidRut={vi.fn()}
      />,
    );

    expect(screen.getByText(/importados desde ChileRUT Empresa/i)).toBeInTheDocument();
  });

  it("no consulta la fuente con un RUT de dígito verificador incorrecto", () => {
    const onInvalidRut = vi.fn();
    render(
      <CompanyImportCard
        rut="76.668.304-0"
        imported={null}
        onImported={vi.fn()}
        onInvalidRut={onInvalidRut}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /importar datos/i }));

    expect(importCompanyProfileMock).not.toHaveBeenCalled();
    expect(onInvalidRut).toHaveBeenCalledWith(
      "El RUT no es válido. Revisa el dígito verificador.",
    );
  });

  it("no consulta la fuente con el RUT vacío", () => {
    const onInvalidRut = vi.fn();
    render(
      <CompanyImportCard rut="" imported={null} onImported={vi.fn()} onInvalidRut={onInvalidRut} />,
    );

    fireEvent.click(screen.getByRole("button", { name: /importar datos/i }));

    expect(importCompanyProfileMock).not.toHaveBeenCalled();
    expect(onInvalidRut).toHaveBeenCalledTimes(1);
  });

  it("muestra el 404 como aviso informativo, sin alerta", async () => {
    importCompanyProfileMock.mockRejectedValue(
      new ApiError(404, "No encontramos datos para el RUT 76668304-5."),
    );
    const onImported = vi.fn();
    render(
      <CompanyImportCard
        rut="76.668.304-5"
        imported={null}
        onImported={onImported}
        onInvalidRut={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /importar datos/i }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "No encontramos datos para el RUT 76668304-5.",
    );
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(onImported).not.toHaveBeenCalled();
  });

  it.each([502, 503])("muestra el %s como advertencia", async (status) => {
    importCompanyProfileMock.mockRejectedValue(new ApiError(status, "La fuente no responde."));
    render(
      <CompanyImportCard
        rut="76.668.304-5"
        imported={null}
        onImported={vi.fn()}
        onInvalidRut={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /importar datos/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("La fuente no responde.");
  });

  it("muestra el timeout como advertencia", async () => {
    importCompanyProfileMock.mockRejectedValue(new TimeoutError());
    render(
      <CompanyImportCard
        rut="76.668.304-5"
        imported={null}
        onImported={vi.fn()}
        onInvalidRut={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /importar datos/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(new TimeoutError().message);
  });

  it("muestra un mensaje genérico cuando falla la red", async () => {
    importCompanyProfileMock.mockRejectedValue(new TypeError("Failed to fetch"));
    render(
      <CompanyImportCard
        rut="76.668.304-5"
        imported={null}
        onImported={vi.fn()}
        onInvalidRut={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /importar datos/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/no pudimos importar/i);
  });

  it("borra el aviso anterior al importar de nuevo", async () => {
    importCompanyProfileMock.mockRejectedValueOnce(new ApiError(503, "La fuente no responde."));
    importCompanyProfileMock.mockResolvedValueOnce(IMPORTED);
    render(
      <CompanyImportCard
        rut="76.668.304-5"
        imported={null}
        onImported={vi.fn()}
        onInvalidRut={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /importar datos/i }));
    await screen.findByRole("alert");
    fireEvent.click(screen.getByRole("button", { name: /importar datos/i }));

    await vi.waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
  });
});
