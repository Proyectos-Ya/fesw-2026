import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { QuotationEditor } from "../QuotationEditor";
import { ApiError, apiFetch } from "@/features/shared/api/client";

vi.mock("@/features/shared/api/client", async importOriginal => {
  const original = await importOriginal<typeof import("@/features/shared/api/client")>();
  return { ...original, apiFetch: vi.fn() };
});
const saved = { id: "quote", supplier_id: "company", tender_id: "tender", currency: "CLP", items: [{ description: "Cemento", unit: "saco", quantity: "2.5", unit_price: "100.25" }], total: "250.63", updated_at: "2026-09-16T12:00:00Z" };

async function open() {
  render(<QuotationEditor tenderId="tender" tenderCode="123-45" />);
  fireEvent.click(screen.getByRole("button", { name: "Generar cotización" }));
  await screen.findByLabelText("Descripción 1");
}

describe("editor de cotización", () => {
  beforeEach(() => { vi.clearAllMocks(); });
  it("bloquea guardar y descargar con campos incompletos", async () => {
    vi.mocked(apiFetch).mockRejectedValueOnce(new ApiError(404, "No existe"));
    await open();
    fireEvent.click(screen.getByRole("button", { name: "Guardar cotización" }));
    expect(screen.getByRole("alert")).toHaveTextContent("descripción");
    fireEvent.click(screen.getByRole("button", { name: "Descargar CSV" }));
    expect(apiFetch).toHaveBeenCalledTimes(1);
  });
  it("consulta, edita y guarda; conserva el borrador al cerrar el panel", async () => {
    vi.mocked(apiFetch).mockResolvedValue(saved);
    await open();
    expect(screen.getByLabelText("Descripción 1")).toHaveValue("Cemento");
    fireEvent.change(screen.getByLabelText("Cantidad 1"), { target: { value: "3" } });
    expect(screen.getByLabelText("Subtotal 1")).toHaveTextContent("300.75 CLP");
    fireEvent.click(screen.getByRole("button", { name: "Cerrar cotización" }));
    fireEvent.click(screen.getByRole("button", { name: "Generar cotización" }));
    expect(screen.getByLabelText("Cantidad 1")).toHaveValue(3);
    fireEvent.click(screen.getByRole("button", { name: "Guardar cotización" }));
    await screen.findByText("Cotización guardada.");
    expect(apiFetch).toHaveBeenLastCalledWith("/tenders/tender/quotation", { method: "PUT", body: JSON.stringify({ currency: "CLP", items: [{ description: "Cemento", unit: "saco", quantity: "3", unit_price: "100.25" }] }) });
  });
  it("permite agregar y eliminar materiales, rechazando la lista vacía", async () => {
    vi.mocked(apiFetch).mockResolvedValue(saved);
    await open();
    fireEvent.click(screen.getByRole("button", { name: "Agregar material" }));
    expect(screen.getByLabelText("Descripción 2")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Eliminar material 2"));
    fireEvent.click(screen.getByLabelText("Eliminar material 1"));
    fireEvent.click(screen.getByRole("button", { name: "Guardar cotización" }));
    expect(screen.getByRole("alert")).toHaveTextContent("al menos un material");
  });
  it("no permite sobrescribir una cotización que no se pudo cargar", async () => {
    vi.mocked(apiFetch).mockRejectedValue(new ApiError(500, "Servicio no disponible"));
    render(<QuotationEditor tenderId="tender" tenderCode="123-45" />);
    fireEvent.click(screen.getByRole("button", { name: "Generar cotización" }));
    await screen.findByRole("alert");
    expect(screen.queryByRole("button", { name: "Guardar cotización" })).not.toBeInTheDocument();
  });
  it("conserva el borrador y muestra el error si falla el guardado", async () => {
    vi.mocked(apiFetch).mockResolvedValueOnce(saved).mockRejectedValueOnce(new ApiError(503, "Intenta nuevamente"));
    await open();
    fireEvent.click(screen.getByRole("button", { name: "Guardar cotización" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Intenta nuevamente"));
    expect(screen.getByLabelText("Descripción 1")).toHaveValue("Cemento");
  });
});
