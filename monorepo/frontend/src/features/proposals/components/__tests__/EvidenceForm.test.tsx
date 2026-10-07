import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "@/features/shared/api/client";
import { EvidenceForm } from "../EvidenceForm";
import { VIALES } from "../../testing/fixtures";

function renderForm(onSubmit = vi.fn().mockResolvedValue(undefined)) {
  const onClose = vi.fn();
  render(<EvidenceForm open question={VIALES} onClose={onClose} onSubmit={onSubmit} />);
  return { onSubmit, onClose };
}

describe("EvidenceForm", () => {
  it("dice a qué pregunta respalda el proyecto", () => {
    renderForm();

    expect(screen.getByRole("dialog", { name: "Agregar proyecto" })).toHaveTextContent(
      "obras viales",
    );
  });

  it("guarda título, mandante, año, monto y descripción", async () => {
    const { onSubmit, onClose } = renderForm();

    await userEvent.type(screen.getByLabelText("Título del proyecto"), "Repavimentación calle Prat");
    await userEvent.type(screen.getByLabelText("Mandante"), "Municipalidad de Pica");
    await userEvent.type(screen.getByLabelText("Año"), "2024");
    await userEvent.type(screen.getByLabelText(/Monto en CLP/), "12000000");
    await userEvent.type(screen.getByLabelText(/Descripción/), "800 m2 de asfalto");
    await userEvent.click(screen.getByRole("button", { name: "Guardar proyecto" }));

    expect(onSubmit).toHaveBeenCalledWith(VIALES.id, {
      title: "Repavimentación calle Prat",
      buyer: "Municipalidad de Pica",
      year: 2024,
      amount_clp: 12_000_000,
      description: "800 m2 de asfalto",
    });
    expect(onClose).toHaveBeenCalled();
  });

  it("monto y descripción son opcionales", async () => {
    const { onSubmit } = renderForm();

    await userEvent.type(screen.getByLabelText("Título del proyecto"), "Bacheo");
    await userEvent.type(screen.getByLabelText("Mandante"), "Serviu");
    await userEvent.type(screen.getByLabelText("Año"), "2023");
    await userEvent.click(screen.getByRole("button", { name: "Guardar proyecto" }));

    expect(onSubmit).toHaveBeenCalledWith(VIALES.id, {
      title: "Bacheo",
      buyer: "Serviu",
      year: 2023,
      amount_clp: null,
      description: null,
    });
  });

  it("sin título ni año válido no envía", async () => {
    const { onSubmit } = renderForm();

    await userEvent.type(screen.getByLabelText("Año"), "1700");
    await userEvent.click(screen.getByRole("button", { name: "Guardar proyecto" }));

    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByText("Escribe el título del proyecto.")).toBeInTheDocument();
    expect(screen.getByText("Escribe quién encargó el proyecto.")).toBeInTheDocument();
    expect(screen.getByText(/Indica un año entre 1900 y/)).toBeInTheDocument();
  });

  it.each([
    [409, /respondido "Sí"/],
    [422, /no son válidos/],
  ])("un %i se muestra en el formulario y no lo cierra", async (status, texto) => {
    const { onClose } = renderForm(vi.fn().mockRejectedValue(new ApiError(status, "x")));

    await userEvent.type(screen.getByLabelText("Título del proyecto"), "Bacheo");
    await userEvent.type(screen.getByLabelText("Mandante"), "Serviu");
    await userEvent.type(screen.getByLabelText("Año"), "2023");
    await userEvent.click(screen.getByRole("button", { name: "Guardar proyecto" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(texto);
    expect(onClose).not.toHaveBeenCalled();
  });

  it("se puede cerrar sin guardar", async () => {
    const { onClose, onSubmit } = renderForm();

    await userEvent.click(screen.getByRole("button", { name: "Cancelar" }));

    expect(onClose).toHaveBeenCalled();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
