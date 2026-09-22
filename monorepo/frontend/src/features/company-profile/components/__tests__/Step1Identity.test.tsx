import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Step1Identity } from "../steps/Step1Identity";

const checkRutExistsMock = vi.fn();

vi.mock("../../services/supplierService", () => ({
  checkRutExists: (rut: string) => checkRutExistsMock(rut) as Promise<boolean>,
}));

function renderStep(defaultValues = {}) {
  const onNext = vi.fn();
  render(
    <Step1Identity
      defaultValues={defaultValues}
      adminName="Ana Pérez"
      onNext={onNext}
      onBack={vi.fn()}
    />,
  );
  return { onNext };
}

describe("Step1Identity (RUT)", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("da formato XX.XXX.XXX-X al RUT mientras se escribe", async () => {
    renderStep();
    const input = screen.getByLabelText("RUT de la empresa");

    await userEvent.type(input, "761234560");

    expect(input).toHaveValue("76.123.456-0");
  });

  it("formatea el RUT que llega en los valores iniciales", () => {
    renderStep({ rut: "76123456-0" });

    expect(screen.getByLabelText("RUT de la empresa")).toHaveValue("76.123.456-0");
  });

  it("muestra el error del dígito verificador con un RUT formateado incorrecto", async () => {
    renderStep();
    const input = screen.getByLabelText("RUT de la empresa");

    await userEvent.type(input, "761234567");
    await userEvent.tab();

    expect(
      await screen.findByText("El RUT no es válido. Revisa el dígito verificador."),
    ).toBeInTheDocument();
  });

  it("envía el RUT formateado al avanzar", async () => {
    checkRutExistsMock.mockResolvedValue(false);
    const { onNext } = renderStep();

    await userEvent.type(
      screen.getByLabelText("Nombre de la empresa"),
      "Constructora Pérez Ltda.",
    );
    await userEvent.type(screen.getByLabelText("RUT de la empresa"), "761234560");
    await userEvent.click(screen.getByRole("button", { name: /Siguiente/ }));

    await waitFor(() => expect(onNext).toHaveBeenCalled());
    expect(checkRutExistsMock).toHaveBeenCalledWith("76.123.456-0");
    expect(onNext.mock.calls[0][0]).toMatchObject({ rut: "76.123.456-0" });
  });
});
