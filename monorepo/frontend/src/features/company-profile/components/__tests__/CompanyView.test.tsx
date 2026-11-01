import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CompanyView } from "../CompanyView";
import type { CompanyState } from "../CompanyProvider";
import type { Supplier } from "../../services/supplierService";
import * as WorkspaceContextModule from "@/features/workspaces/WorkspaceContext";
import * as workspaceService from "@/features/workspaces/services/workspaceService";

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

vi.mock("@/features/workspaces/services/workspaceService", () => ({
  listWorkspaceMembers: vi.fn().mockResolvedValue([]),
  listWorkspaceInvitations: vi.fn().mockResolvedValue([]),
  createInvitation: vi.fn(),
  cancelInvitation: vi.fn(),
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
  vi.restoreAllMocks();
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
    expect(screen.getByRole("button", { name: /^editar$/i })).toBeInTheDocument();
  });

  it("muestra la sección de equipo de la empresa cuando el usuario es administrador (CA1)", async () => {
    companyState = { status: "with-company", supplier: SUPPLIER };
    vi.spyOn(WorkspaceContextModule, "useWorkspace").mockReturnValue({
      workspaces: [],
      recentWorkspaces: [],
      activeWorkspace: {
        user_id: "user-1",
        active_supplier_id: "supplier-1",
        active_supplier_name: "Constructora Norte SpA",
        role: "admin",
        permissions: ["invite_members"],
        is_admin: true,
      },
      invitations: [],
      isLoading: false,
      isAdmin: true,
      hasPermission: () => true,
      switchActiveWorkspace: vi.fn(),
      refreshWorkspaces: vi.fn(),
      refreshInvitations: vi.fn(),
      acceptPendingInvitation: vi.fn(),
      rejectPendingInvitation: vi.fn(),
    });
    vi.mocked(workspaceService.listWorkspaceMembers).mockResolvedValueOnce([
      {
        id: "m-1",
        user_id: "user-1",
        supplier_id: "supplier-1",
        email: "admin@norte.cl",
        full_name: "Admin Norte",
        role: "admin",
        status: "active",
        joined_at: "2026-01-01T00:00:00Z",
      },
    ]);

    render(<CompanyView />);

    expect(
      await screen.findByRole("heading", { name: /equipo de la empresa/i }),
    ).toBeInTheDocument();
    expect(await screen.findByText("Admin Norte")).toBeInTheDocument();
  });

  it("al editar y guardar envía los cambios y vuelve al modo lectura", async () => {
    companyState = { status: "with-company", supplier: SUPPLIER };
    const updated = { ...SUPPLIER, legal_name: "Constructora Renovada SpA" };
    updateSupplierMock.mockResolvedValue(updated);
    const user = userEvent.setup();

    render(<CompanyView />);

    await user.click(screen.getByRole("button", { name: /^editar$/i }));
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
      await screen.findByRole("button", { name: /^editar$/i }),
    ).toBeInTheDocument();
  });

  it("cancelar la edición vuelve al modo lectura sin guardar", async () => {
    companyState = { status: "with-company", supplier: SUPPLIER };
    const user = userEvent.setup();

    render(<CompanyView />);

    await user.click(screen.getByRole("button", { name: /^editar$/i }));
    await user.click(screen.getByRole("button", { name: /cancelar/i }));

    expect(updateSupplierMock).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /^editar$/i })).toBeInTheDocument();
  });
});

/** Fecha AAAA-MM-DD local a `offsetDays` días de hoy. */
function dateFromToday(offsetDays: number): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

describe("CompanyView certificaciones", () => {
  const withCertifications = (certifications: Supplier["certifications"]) => {
    companyState = {
      status: "with-company",
      supplier: { ...SUPPLIER, certifications },
    };
  };

  it("muestra badge rojo en una certificación vencida", () => {
    withCertifications([{ name: "ISO 9001", expires_at: dateFromToday(-3) }]);

    render(<CompanyView />);

    const badge = screen.getByText("Vencida");
    expect(badge.className).toMatch(/danger/);
  });

  it("muestra badge ámbar con los días restantes si vence en 30 días o menos", () => {
    withCertifications([
      { name: "ISO 9001", expires_at: dateFromToday(10) },
      { name: "SEC", expires_at: dateFromToday(0) },
    ]);

    render(<CompanyView />);

    expect(screen.getByText("Vence en 10 días").className).toMatch(/warning/);
    expect(screen.getByText("Vence hoy").className).toMatch(/warning/);
  });

  it("no muestra badge si la certificación está vigente o no tiene fecha", () => {
    withCertifications([
      { name: "ISO 9001", expires_at: dateFromToday(90) },
      { name: "SEC", expires_at: null },
      "OHSAS 18001",
    ]);

    render(<CompanyView />);

    expect(screen.getByText("ISO 9001")).toBeInTheDocument();
    expect(screen.getByText("OHSAS 18001")).toBeInTheDocument();
    expect(screen.queryByText("Vencida")).not.toBeInTheDocument();
    expect(screen.queryByText(/^Vence (en|hoy)/)).not.toBeInTheDocument();
  });

  it("edita la fecha de una certificación y guarda la lista actualizada", async () => {
    withCertifications([
      { name: "ISO 9001", expires_at: dateFromToday(-3) },
      { name: "SEC", expires_at: null },
    ]);
    const updated = { ...SUPPLIER, certifications: [] };
    updateSupplierMock.mockResolvedValue(updated);
    const user = userEvent.setup();

    render(<CompanyView />);

    await user.click(screen.getByRole("button", { name: "Editar fecha de ISO 9001" }));
    const input = screen.getByLabelText(/fecha de vencimiento de ISO 9001/i);
    await user.clear(input);
    await user.type(input, "2030-05-20");
    await user.click(screen.getByRole("button", { name: /guardar fecha/i }));

    expect(updateSupplierMock).toHaveBeenCalledOnce();
    expect(updateSupplierMock).toHaveBeenCalledWith({
      certifications: [
        { name: "ISO 9001", expires_at: "2030-05-20" },
        { name: "SEC", expires_at: null },
      ],
    });
    expect(setSupplierMock).toHaveBeenCalledWith(updated);
  });

  it("agrega fecha a una certificación que no tenía", async () => {
    withCertifications(["ISO 9001"]);
    updateSupplierMock.mockResolvedValue(SUPPLIER);
    const user = userEvent.setup();

    render(<CompanyView />);

    await user.click(screen.getByRole("button", { name: "Editar fecha de ISO 9001" }));
    await user.type(screen.getByLabelText(/fecha de vencimiento de ISO 9001/i), "2030-01-31");
    await user.click(screen.getByRole("button", { name: /guardar fecha/i }));

    expect(updateSupplierMock).toHaveBeenCalledWith({
      certifications: [{ name: "ISO 9001", expires_at: "2030-01-31" }],
    });
  });

  it("elimina una certificación tras confirmar y guarda la lista sin ella", async () => {
    withCertifications([
      { name: "ISO 9001", expires_at: null },
      { name: "SEC", expires_at: null },
    ]);
    updateSupplierMock.mockResolvedValue(SUPPLIER);
    const user = userEvent.setup();

    render(<CompanyView />);

    await user.click(screen.getByRole("button", { name: "Eliminar ISO 9001" }));
    expect(updateSupplierMock).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: /confirmar eliminación/i }));

    expect(updateSupplierMock).toHaveBeenCalledWith({
      certifications: [{ name: "SEC", expires_at: null }],
    });
    expect(setSupplierMock).toHaveBeenCalledWith(SUPPLIER);
  });

  it("cancelar la confirmación no elimina nada", async () => {
    withCertifications([{ name: "ISO 9001", expires_at: null }]);
    const user = userEvent.setup();

    render(<CompanyView />);

    await user.click(screen.getByRole("button", { name: "Eliminar ISO 9001" }));
    await user.click(screen.getByRole("button", { name: /cancelar/i }));

    expect(updateSupplierMock).not.toHaveBeenCalled();
    expect(screen.queryByText(/¿eliminar esta certificación/i)).not.toBeInTheDocument();
  });

  it("muestra el error si falla el guardado y no actualiza la empresa", async () => {
    withCertifications([{ name: "ISO 9001", expires_at: null }]);
    updateSupplierMock.mockRejectedValue(new Error("boom"));
    const user = userEvent.setup();

    render(<CompanyView />);

    await user.click(screen.getByRole("button", { name: "Eliminar ISO 9001" }));
    await user.click(screen.getByRole("button", { name: /confirmar eliminación/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /no se pudo guardar la certificación/i,
    );
    expect(setSupplierMock).not.toHaveBeenCalled();
  });
});
