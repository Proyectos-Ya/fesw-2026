import React from "react";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CompanyProvider, useCompany } from "../CompanyProvider";
import { ApiError } from "@/features/shared/api/client";
import type { Supplier } from "../../services/supplierService";

const getMySupplierMock = vi.fn();

vi.mock("../../services/supplierService", () => ({
  getMySupplier: () => getMySupplierMock() as Promise<Supplier>,
}));

const SUPPLIER = {
  id: "supplier-1",
  legal_name: "Constructora Norte SpA",
} as Supplier;

function ShowCompany() {
  const { company } = useCompany();
  if (company.status === "with-company") {
    return <span>{company.supplier.legal_name}</span>;
  }
  return <span>{company.status}</span>;
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("CompanyProvider", () => {
  it("expone la empresa devuelta por GET /suppliers/me", async () => {
    getMySupplierMock.mockResolvedValue(SUPPLIER);

    render(
      <CompanyProvider>
        <ShowCompany />
      </CompanyProvider>,
    );

    expect(await screen.findByText("Constructora Norte SpA")).toBeInTheDocument();
  });

  it("expone without-company cuando el backend responde 404", async () => {
    getMySupplierMock.mockRejectedValue(new ApiError(404, "Sin empresa"));

    render(
      <CompanyProvider>
        <ShowCompany />
      </CompanyProvider>,
    );

    expect(await screen.findByText("without-company")).toBeInTheDocument();
  });

  it("expone error ante fallas inesperadas del backend", async () => {
    getMySupplierMock.mockRejectedValue(new ApiError(500, "Error interno"));

    render(
      <CompanyProvider>
        <ShowCompany />
      </CompanyProvider>,
    );

    expect(await screen.findByText("error")).toBeInTheDocument();
  });

  it("useCompany lanza error si se usa fuera del provider", () => {
    expect(() => render(<ShowCompany />)).toThrow(
      "useCompany debe usarse dentro de <CompanyProvider>",
    );
  });
});
