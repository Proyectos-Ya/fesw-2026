import React from "react";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HomeView } from "../HomeView";
import type { CompanyState } from "../CompanyProvider";
import type { Supplier } from "../../services/supplierService";

vi.mock("@/features/auth/components/SessionProvider", () => ({
  useSession: () => ({
    user: {
      id: "user-1",
      email: "ana@example.com",
      full_name: "Ana Pérez",
      phone: null,
      active: true,
      email_verified: false,
      created_at: "2026-01-01T00:00:00Z",
    },
    isLoading: false,
    logout: vi.fn(),
  }),
}));

let companyState: CompanyState = { status: "loading" };

vi.mock("../CompanyProvider", () => ({
  useCompany: () => ({
    company: companyState,
    setSupplier: vi.fn(),
    refresh: vi.fn(),
  }),
}));

const SUPPLIER = {
  id: "supplier-1",
  legal_name: "Constructora Norte SpA",
} as Supplier;

afterEach(() => {
  vi.clearAllMocks();
});

describe("HomeView", () => {
  it("sin empresa muestra las opciones de crear y unirse con sus rutas", () => {
    companyState = { status: "without-company" };

    render(<HomeView />);

    const crear = screen.getByRole("link", { name: /crear mi empresa/i });
    expect(crear).toHaveAttribute("href", "/empresa/crear");

    const unirse = screen.getByRole("link", { name: /unirse a una empresa/i });
    expect(unirse).toHaveAttribute("href", "/empresa/unirse");
  });

  it("con empresa saluda al usuario y muestra el nombre de la empresa", () => {
    companyState = { status: "with-company", supplier: SUPPLIER };

    render(<HomeView />);

    expect(screen.getByText(/Hola, Ana Pérez/)).toBeInTheDocument();
    expect(screen.getByText("Constructora Norte SpA")).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /crear mi empresa/i }),
    ).not.toBeInTheDocument();
  });

  it("ante un error inesperado muestra un mensaje de recarga", () => {
    companyState = { status: "error" };

    render(<HomeView />);

    expect(
      screen.getByText(/No pudimos cargar tu información/),
    ).toBeInTheDocument();
  });
});
