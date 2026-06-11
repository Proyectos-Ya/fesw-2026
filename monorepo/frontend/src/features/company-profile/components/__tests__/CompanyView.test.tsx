import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CompanyView } from "../CompanyView";
import type { CompanyState } from "../CompanyProvider";
import type { Supplier } from "../../services/supplierService";

let companyState: CompanyState = { status: "loading" };
const setSupplierMock = vi.fn();

vi.mock("../CompanyProvider", () => ({
  useCompany: () => ({
    company: companyState,
    setSupplier: setSupplierMock,
    refresh: vi.fn(),
  }),
}));

const updateSupplierMock = vi.fn();

vi.mock("../../services/supplierService", () => ({
  updateSupplier: (data: unknown) => updateSupplierMock(data) as Promise<Supplier>,
}));

const SUPPLIER: Supplier = {
  id: "supplier-1",
  user_id: "user-1",
  rut: "76.086.428-5",
  legal_name: "Constructora Norte SpA",
  trade_name: null,
  description: "Empresa con amplia experiencia en obras civiles y montaje.",
  regions: ["Valparaíso"],
  sectors: ["Desarrollo de Software"],
  certifications: ["ISO 9001"],
  keywords: ["obras"],
  years_experience: 5,
  num_employees: 20,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

afterEach(() => {
  vi.clearAllMocks();
});

describe("CompanyView", () => {
  it("sin empresa invita a crearla con el enlace a /empresa/crear", () => {
    companyState = { status: "without-company" };

    render(<CompanyView />);

    expect(
      screen.getByRole("link", { name: /crear mi empresa/i }),
    ).toHaveAttribute("href", "/empresa/crear");
  });

  it("muestra toda la información de la empresa en modo lectura", () => {
    companyState = { status: "with-company", supplier: SUPPLIER };

    render(<CompanyView />);

    expect(screen.getByText("Constructora Norte SpA")).toBeInTheDocument();
    expect(screen.getByText(/RUT 76\.086\.428-5/)).toBeInTheDocument();
    expect(screen.getByText("Valparaíso")).toBeInTheDocument();
    expect(screen.getByText("ISO 9001")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /editar/i })).toBeInTheDocument();
  });

  it("al editar y guardar envía los cambios y vuelve al modo lectura", async () => {
    companyState = { status: "with-company", supplier: SUPPLIER };
    const updated = { ...SUPPLIER, legal_name: "Constructora Renovada SpA" };
    updateSupplierMock.mockResolvedValue(updated);
    const user = userEvent.setup();

    render(<CompanyView />);

    await user.click(screen.getByRole("button", { name: /editar/i }));
    // El RUT aparece como no editable en el formulario
    expect(screen.getByText(/no editable/i)).toBeInTheDocument();

    const legalName = screen.getByLabelText(/razón social/i);
    await user.clear(legalName);
    await user.type(legalName, "Constructora Renovada SpA");
    await user.click(screen.getByRole("button", { name: /guardar cambios/i }));

    expect(updateSupplierMock).toHaveBeenCalledOnce();
    expect(updateSupplierMock.mock.calls[0][0]).toMatchObject({
      legal_name: "Constructora Renovada SpA",
    });
    expect(setSupplierMock).toHaveBeenCalledWith(updated);
    // Vuelve al modo lectura
    expect(
      await screen.findByRole("button", { name: /editar/i }),
    ).toBeInTheDocument();
  });

  it("cancelar la edición vuelve al modo lectura sin guardar", async () => {
    companyState = { status: "with-company", supplier: SUPPLIER };
    const user = userEvent.setup();

    render(<CompanyView />);

    await user.click(screen.getByRole("button", { name: /editar/i }));
    await user.click(screen.getByRole("button", { name: /cancelar/i }));

    expect(updateSupplierMock).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /editar/i })).toBeInTheDocument();
  });
});
