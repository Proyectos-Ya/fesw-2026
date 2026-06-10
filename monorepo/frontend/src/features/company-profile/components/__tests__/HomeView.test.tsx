import React from "react";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HomeView } from "../HomeView";
import { ApiError } from "@/features/shared/api/client";
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

const getMySupplierMock = vi.fn();

vi.mock("../../services/supplierService", () => ({
  getMySupplier: () => getMySupplierMock() as Promise<Supplier>,
}));

const SUPPLIER = {
  id: "supplier-1",
  legal_name: "Constructora Norte SpA",
} as Supplier;

afterEach(() => {
  vi.clearAllMocks();
});

describe("HomeView", () => {
  it("sin empresa muestra las opciones de crear y unirse con sus rutas", async () => {
    getMySupplierMock.mockRejectedValue(new ApiError(404, "Sin empresa"));

    render(<HomeView />);

    const crear = await screen.findByRole("link", { name: /crear mi empresa/i });
    expect(crear).toHaveAttribute("href", "/empresa/crear");

    const unirse = screen.getByRole("link", { name: /unirse a una empresa/i });
    expect(unirse).toHaveAttribute("href", "/empresa/unirse");
  });

  it("con empresa saluda al usuario y muestra el nombre de la empresa", async () => {
    getMySupplierMock.mockResolvedValue(SUPPLIER);

    render(<HomeView />);

    expect(await screen.findByText(/Hola, Ana Pérez/)).toBeInTheDocument();
    expect(screen.getByText("Constructora Norte SpA")).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /crear mi empresa/i }),
    ).not.toBeInTheDocument();
  });

  it("ante un error inesperado muestra un mensaje de recarga", async () => {
    getMySupplierMock.mockRejectedValue(new ApiError(500, "Error interno"));

    render(<HomeView />);

    expect(
      await screen.findByText(/No pudimos cargar tu información/),
    ).toBeInTheDocument();
  });
});
