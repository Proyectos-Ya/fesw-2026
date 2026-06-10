import React from "react";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HomeView } from "../HomeView";
import type { CompanyState } from "../CompanyProvider";
import type { Supplier } from "../../services/supplierService";
import type { UserPublic } from "@/features/auth/authSchema";

const replaceMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: replaceMock,
    push: vi.fn(),
  }),
}));

const USER: UserPublic = {
  id: "user-1",
  email: "ana@example.com",
  full_name: "Ana Pérez",
  phone: null,
  active: true,
  email_verified: false,
  created_at: "2026-01-01T00:00:00Z",
};

let authState: {
  user: UserPublic | null;
  isLoading: boolean;
  isAuthenticated: boolean;
} = { user: USER, isLoading: false, isAuthenticated: true };

vi.mock("@/features/auth/AuthContext", () => ({
  useAuth: () => ({
    ...authState,
    refresh: vi.fn(),
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
  it("muestra el estado de carga mientras se valida la sesión o la empresa", () => {
    authState = { user: USER, isLoading: false, isAuthenticated: true };
    companyState = { status: "loading" };

    render(<HomeView />);

    expect(screen.getByText(/Cargando/)).toBeInTheDocument();
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("redirige a /login si no hay sesión activa", () => {
    authState = { user: null, isLoading: false, isAuthenticated: false };
    companyState = { status: "loading" };

    render(<HomeView />);

    expect(replaceMock).toHaveBeenCalledWith("/login");
  });

  it("sin empresa invita a construir el perfil inteligente", () => {
    authState = { user: USER, isLoading: false, isAuthenticated: true };
    companyState = { status: "without-company" };

    render(<HomeView />);

    expect(screen.getByText(/Hola, Ana/)).toBeInTheDocument();
    const cta = screen.getByRole("link", {
      name: /construir mi perfil inteligente/i,
    });
    expect(cta).toHaveAttribute("href", "/perfil");
  });

  it("con empresa muestra el placeholder de licitaciones con el nombre de la empresa", () => {
    authState = { user: USER, isLoading: false, isAuthenticated: true };
    companyState = { status: "with-company", supplier: SUPPLIER };

    render(<HomeView />);

    expect(
      screen.getByText(/Recomendadas para Constructora Norte SpA/),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /construir mi perfil inteligente/i }),
    ).not.toBeInTheDocument();
  });

  it("ante un error inesperado muestra un mensaje de recarga", () => {
    authState = { user: USER, isLoading: false, isAuthenticated: true };
    companyState = { status: "error" };

    render(<HomeView />);

    expect(
      screen.getByText(/No pudimos cargar tu información/),
    ).toBeInTheDocument();
  });
});
