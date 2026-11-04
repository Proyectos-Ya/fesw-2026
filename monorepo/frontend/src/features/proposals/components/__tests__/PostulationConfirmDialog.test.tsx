import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { PostulationPackage } from "../../types";
import { PostulationConfirmDialog } from "../PostulationConfirmDialog";

describe("PostulationConfirmDialog (CA3, CA4)", () => {
  const samplePackage: PostulationPackage = {
    tender: {
      id: "t-1",
      code: "2499-12-L126",
      title: "Adquisición de Insumos Médicos",
      closing_at: "2026-12-31T23:59:59Z",
      url: "https://mercadopublico.cl",
    },
    company: {
      rut: "76.086.428-5",
      name: "Inversiones Médicas SpA",
      contact_name: "Juan Perez",
      contact_email: "juan@medicas.cl",
      contact_phone: "+56912345678",
    },
    items: [
      {
        line_number: 1,
        name: "Guantes de Látex",
        quantity: 100,
        unit: "Caja",
        suggested_unit_price: 3500,
        suggested_total_price: 350000,
        technical_spec: "Caja x 100",
      },
    ],
    total_suggested_clp: 350000,
    observations: "Oferta conforme a bases.",
    validity_days: 60,
    delivery_term_days: 10,
    required_documents: [],
  };

  it("renderiza datos de licitación, empresa, precios cargados automáticamente y total", () => {
    render(
      <PostulationConfirmDialog
        open={true}
        packageData={samplePackage}
        busy={false}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />
    );

    expect(screen.getAllByText(/2499-12-L126/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Inversiones Médicas SpA/i)).toBeInTheDocument();
    expect(screen.getByText(/76.086.428-5/i)).toBeInTheDocument();
    expect(screen.getByText(/\$3\.500/i)).toBeInTheDocument();
    expect(screen.getAllByText(/\$350\.000/i).length).toBeGreaterThan(0);
  });

  it("requiere marcar la casilla de revisión rigurosa para habilitar la confirmación", () => {
    render(
      <PostulationConfirmDialog
        open={true}
        packageData={samplePackage}
        busy={false}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />
    );

    const confirmBtn = screen.getByRole("button", { name: /Confirmar y Cargar en Mercado Público/i });
    expect(confirmBtn).toBeDisabled();

    const checkbox = screen.getByRole("checkbox", { name: /He revisado rigurosamente/i });
    fireEvent.click(checkbox);

    expect(confirmBtn).not.toBeDisabled();
  });

  it("bloquea confirmación si el monto total es cero", () => {
    const zeroPackage: PostulationPackage = {
      ...samplePackage,
      items: [
        {
          ...samplePackage.items[0],
          suggested_unit_price: 0,
        },
      ],
    };

    render(
      <PostulationConfirmDialog
        open={true}
        packageData={zeroPackage}
        busy={false}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />
    );

    const checkbox = screen.getByRole("checkbox", { name: /He revisado rigurosamente/i });
    fireEvent.click(checkbox);

    const confirmBtn = screen.getByRole("button", { name: /Confirmar y Cargar en Mercado Público/i });
    expect(confirmBtn).toBeDisabled();
    expect(screen.getByText(/Falta ingresar precios en la cotización/i)).toBeInTheDocument();
  });

  it("ejecuta onConfirm con los datos cargados automáticamente al confirmar tras marcar la revisión", () => {
    const onConfirmMock = vi.fn();
    render(
      <PostulationConfirmDialog
        open={true}
        packageData={samplePackage}
        busy={false}
        onClose={vi.fn()}
        onConfirm={onConfirmMock}
      />
    );

    const checkbox = screen.getByRole("checkbox", { name: /He revisado rigurosamente/i });
    fireEvent.click(checkbox);

    const confirmBtn = screen.getByRole("button", { name: /Confirmar y Cargar en Mercado Público/i });
    fireEvent.click(confirmBtn);

    expect(onConfirmMock).toHaveBeenCalledWith(
      expect.objectContaining({
        tender_code: "2499-12-L126",
        company_rut: "76.086.428-5",
        total_clp: 350000,
        observations: "Oferta conforme a bases.",
        delivery_term_days: 10,
        validity_days: 60,
      })
    );
  });

  it("tolera packageData con observations undefined y campos del backend", () => {
    const backendPackage: PostulationPackage = {
      tender: {
        id: "t-2",
        code: "1234-56-L126",
        name: "Servicios de Mantenimiento",
      },
      company: {
        rut: "77.123.456-7",
        legal_name: "Soluciones Integrales S.A.",
        trade_name: "Soluciones SpA",
      },
      offer_name: "Propuesta de Mantenimiento",
      offer_description: "Oferta técnica detallada",
      items: [
        {
          position: 1,
          name: "Servicio Mensual",
          quantity: 2,
          unit_of_measure: "mes",
          unit_price: 50000,
        },
      ],
    };

    render(
      <PostulationConfirmDialog
        open={true}
        packageData={backendPackage}
        busy={false}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />
    );

    expect(screen.getAllByText(/1234-56-L126/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Soluciones SpA/i)).toBeInTheDocument();
    expect(screen.getByText(/Oferta técnica detallada/i)).toBeInTheDocument();
    expect(screen.getByText(/\$50\.000/i)).toBeInTheDocument();
    expect(screen.getAllByText(/\$100\.000/i).length).toBeGreaterThan(0);
  });
});
