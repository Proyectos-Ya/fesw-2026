import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CompanyProvider, useCompany } from "../CompanyProvider";
import { ApiError } from "@/features/shared/api/client";
import type { Supplier } from "../../services/supplierService";
import * as WorkspaceContextModule from "@/features/workspaces/WorkspaceContext";

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
  vi.restoreAllMocks();
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

  it("refresca la empresa cuando cambia active_supplier_id en el WorkspaceContext (CA6)", async () => {
    getMySupplierMock
      .mockRejectedValueOnce(new ApiError(404, "Sin empresa"))
      .mockResolvedValueOnce(SUPPLIER);

    const spy = vi.spyOn(WorkspaceContextModule, "useWorkspace");
    spy.mockReturnValue({
      workspaces: [],
      recentWorkspaces: [],
      activeWorkspace: null,
      invitations: [],
      isLoading: false,
      isAdmin: false,
      hasPermission: () => false,
      switchActiveWorkspace: async () => {},
      refreshWorkspaces: async () => {},
      refreshInvitations: async () => {},
      acceptPendingInvitation: async () => {},
      rejectPendingInvitation: async () => {},
    });

    const { rerender } = render(
      <CompanyProvider>
        <ShowCompany />
      </CompanyProvider>,
    );

    expect(await screen.findByText("without-company")).toBeInTheDocument();

    spy.mockReturnValue({
      workspaces: [],
      recentWorkspaces: [],
      activeWorkspace: {
        user_id: "u-1",
        active_supplier_id: "supplier-1",
        active_supplier_name: "Constructora Norte SpA",
        role: "member",
        permissions: ["view_matches"],
        is_admin: false,
      },
      invitations: [],
      isLoading: false,
      isAdmin: false,
      hasPermission: () => false,
      switchActiveWorkspace: async () => {},
      refreshWorkspaces: async () => {},
      refreshInvitations: async () => {},
      acceptPendingInvitation: async () => {},
      rejectPendingInvitation: async () => {},
    });

    rerender(
      <CompanyProvider>
        <ShowCompany />
      </CompanyProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("Constructora Norte SpA")).toBeInTheDocument();
    });
  });

  it("useCompany lanza error si se usa fuera del provider", () => {
    expect(() => render(<ShowCompany />)).toThrow(
      "useCompany debe usarse dentro de <CompanyProvider>",
    );
  });
});
