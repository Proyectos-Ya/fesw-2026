import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { QuotationEditor } from "../QuotationEditor";
import { ApiError, apiFetch } from "@/features/shared/api/client";

vi.mock("@/features/shared/api/client", async importOriginal => {
  const original = await importOriginal<typeof import("@/features/shared/api/client")>();
  return { ...original, apiFetch: vi.fn() };
});
const saved = { id: "quote", supplier_id: "company", tender_id: "tender", currency: "CLP", items: [{ description: "Cemento", unit: "saco", quantity: "2", unit_price: "100" }], total: "200", updated_at: "2026-09-16T12:00:00Z" };

beforeEach(() => { vi.resetAllMocks(); });

async function open() {
  render(<QuotationEditor tenderId="tender" tenderCode="123-45" tenderItems={[]} />);
  fireEvent.click(screen.getByRole("button", { name: "Generar cotización" }));
  await screen.findByLabelText("Descripción 1");
}

describe("editor de cotización", () => {
  it("precarga materiales y cantidades de la licitación y pide precio en CLP", async () => {
    vi.mocked(apiFetch).mockRejectedValueOnce(new ApiError(404, "No existe"));
    render(<QuotationEditor tenderId="tender" tenderCode="123-45" tenderItems={[{ name: "Cemento", description: "Cemento Portland", unit_of_measure: "saco", quantity: 4 }, { name: "Arena", description: null }]} />);
    fireEvent.click(screen.getByRole("button", { name: "Generar cotización" }));
    expect(await screen.findByDisplayValue("Cemento Portland")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Arena")).toBeInTheDocument();
    expect(screen.getByLabelText("Cantidad 1")).toHaveValue(4);
    expect(screen.getByLabelText("Precio unitario 1")).toHaveValue(null);
    expect(screen.queryByLabelText("Moneda")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Unidad 1")).toHaveValue("saco");
    fireEvent.change(screen.getByLabelText("Cantidad 1"), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText("Precio unitario 1"), { target: { value: "100" } });
    fireEvent.click(screen.getByLabelText("Eliminar material 2"));
    vi.mocked(apiFetch).mockResolvedValueOnce(saved);
    fireEvent.click(screen.getByRole("button", { name: "Guardar cotización" }));
    await screen.findByText("Cotización guardada.");
    expect(apiFetch).toHaveBeenLastCalledWith("/tenders/tender/quotation", { method: "PUT", body: JSON.stringify({ currency: "CLP", items: [{ description: "Cemento Portland", unit: "saco", quantity: "2", unit_price: "100" }] }) });
  });

  it("bloquea guardar y descargar con campos incompletos", async () => {
    vi.mocked(apiFetch).mockRejectedValueOnce(new ApiError(404, "No existe"));
    await open();
    fireEvent.click(screen.getByRole("button", { name: "Guardar cotización" }));
    expect(screen.getByRole("alert")).toHaveTextContent("descripción");
    fireEvent.click(screen.getByRole("button", { name: "Descargar CSV" }));
    fireEvent.click(screen.getByRole("button", { name: "Descargar PDF" }));
    expect(apiFetch).toHaveBeenCalledTimes(1);
  });
  it("consulta, edita y guarda; conserva el borrador al cerrar el panel", async () => {
    vi.mocked(apiFetch).mockResolvedValue(saved);
    await open();
    expect(screen.getByLabelText("Descripción 1")).toHaveValue("Cemento");
    fireEvent.change(screen.getByLabelText("Cantidad 1"), { target: { value: "3" } });
    expect(screen.getByLabelText("Subtotal 1")).toHaveTextContent("300 CLP");
    fireEvent.click(screen.getByRole("button", { name: "Cerrar cotización" }));
    fireEvent.click(screen.getByRole("button", { name: "Generar cotización" }));
    expect(screen.getByLabelText("Cantidad 1")).toHaveValue(3);
    fireEvent.click(screen.getByRole("button", { name: "Guardar cotización" }));
    await screen.findByText("Cotización guardada.");
    expect(apiFetch).toHaveBeenLastCalledWith("/tenders/tender/quotation", { method: "PUT", body: JSON.stringify({ currency: "CLP", items: [{ description: "Cemento", unit: "saco", quantity: "3", unit_price: "100" }] }) });
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
  it("respeta la cotización guardada en lugar de regenerarla", async () => {
    vi.mocked(apiFetch).mockResolvedValue(saved);
    render(<QuotationEditor tenderId="tender" tenderCode="123-45" tenderItems={[{ name: "Arena", description: null }]} />);
    fireEvent.click(screen.getByRole("button", { name: "Generar cotización" }));
    expect(await screen.findByDisplayValue("Cemento")).toBeInTheDocument();
    expect(screen.queryByDisplayValue("Arena")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Cantidad 1")).toHaveValue(2);
  });
  it("no convierte silenciosamente cotizaciones antiguas de otra moneda", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ ...saved, currency: "USD" });
    render(<QuotationEditor tenderId="tender" tenderCode="123-45" />);
    fireEvent.click(screen.getByRole("button", { name: "Generar cotización" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("USD");
    expect(screen.queryByRole("button", { name: "Guardar cotización" })).not.toBeInTheDocument();
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

it("marca los cuatro campos obligatorios y bloquea fracciones antiguas", async () => {
  vi.mocked(apiFetch).mockResolvedValueOnce({...saved, items: [{...saved.items[0], quantity: "2.5"}]});
  await open();
  expect(screen.getAllByText(/\(obligatorio\)/)).toHaveLength(4);
  for (const label of ["Descripción 1", "Unidad 1", "Cantidad 1", "Precio unitario 1"]) expect(screen.getByLabelText(label)).toBeRequired();
  fireEvent.click(screen.getByRole("button", {name: "Descargar PDF"}));
  expect(screen.getByRole("alert")).toHaveTextContent("entero");
  expect(apiFetch).toHaveBeenCalledTimes(1);
});

it("normaliza ceros decimales almacenados sin redondear", async () => {
  vi.mocked(apiFetch).mockResolvedValueOnce({...saved, items: [{...saved.items[0], quantity: "2.000", unit_price: "100.00"}]});
  await open();
  expect(screen.getByLabelText("Cantidad 1")).toHaveValue(2);
  expect(screen.getByLabelText("Precio unitario 1")).toHaveValue(100);
  expect(screen.getByLabelText("Subtotal 1")).toHaveTextContent("200 CLP");
});
it("no descarga PDF si falla el guardado y conserva el borrador", async () => {
  vi.mocked(apiFetch).mockResolvedValueOnce(saved).mockRejectedValueOnce(new ApiError(503, "No se pudo guardar"));
  await open();
  fireEvent.change(screen.getByLabelText("Cantidad 1"), {target: {value: "4"}});
  fireEvent.click(screen.getByRole("button", {name: "Descargar PDF"}));
  expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo guardar");
  expect(screen.getByLabelText("Cantidad 1")).toHaveValue(4);
  expect(screen.getByText("Cambios sin guardar.")).toBeInTheDocument();
});
