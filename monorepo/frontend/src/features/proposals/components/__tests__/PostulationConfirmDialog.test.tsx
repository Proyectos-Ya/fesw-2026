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

  it("renderiza datos de licitación, empresa, precios editables y total", () => {
    render(
      <PostulationConfirmDialog
        open={true}
        packageData={samplePackage}
        busy={false}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />
    );

    expect(screen.getByText(/2499-12-L126/i)).toBeInTheDocument();
    expect(screen.getByText(/Inversiones Médicas SpA/i)).toBeInTheDocument();
    expect(screen.getByText(/76.086.428-5/i)).toBeInTheDocument();
    expect(screen.getByDisplayValue("3500")).toBeInTheDocument();
  });

  it("permite editar el precio unitario y recalcula el total", () => {
    render(
      <PostulationConfirmDialog
        open={true}
        packageData={samplePackage}
        busy={false}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />
    );

    const inputPrecio = screen.getByDisplayValue("3500");
    fireEvent.change(inputPrecio, { target: { value: "4000" } });

    // 4000 * 100 = 400.000
    expect(screen.getAllByText(/\$400\.000/i).length).toBeGreaterThan(0);
  });

  it("bloquea confirmación si el texto de observaciones supera 255 caracteres", () => {
    const longText = "a".repeat(256);
    render(
      <PostulationConfirmDialog
        open={true}
        packageData={{ ...samplePackage, observations: longText }}
        busy={false}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />
    );

    const confirmBtn = screen.getByRole("button", { name: /Confirmar y Cargar en Mercado Público/i });
    expect(confirmBtn).toBeDisabled();
    expect(screen.getByText(/Supera los 255 caracteres/i)).toBeInTheDocument();
  });

  it("ejecuta onConfirm con los datos actualizados al confirmar", () => {
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

    const confirmBtn = screen.getByRole("button", { name: /Confirmar y Cargar en Mercado Público/i });
    fireEvent.click(confirmBtn);

    expect(onConfirmMock).toHaveBeenCalledWith(
      expect.objectContaining({
        tender_code: "2499-12-L126",
        company_rut: "76.086.428-5",
        total_clp: 350000,
      })
    );
  });
});
