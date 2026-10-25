import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Step1Identity } from "../steps/Step1Identity";
import { ApiError } from "@/features/shared/api/client";
import type { CompanyProfileImport } from "../../services/supplierService";
import type { ReviewStatus } from "../../hooks/useProfileWizard";

const checkRutExistsMock = vi.fn();
const importCompanyProfileMock = vi.fn();

vi.mock("../../services/supplierService", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../services/supplierService")>()),
  checkRutExists: (rut: string) => checkRutExistsMock(rut) as Promise<boolean>,
  importCompanyProfile: (rut: string) =>
    importCompanyProfileMock(rut) as Promise<CompanyProfileImport>,
}));

const IMPORTED: CompanyProfileImport = {
  source: "sre",
  rut: "76668304-5",
  legal_name: "Planeta Libre Soluciones Sustentables Limitada",
  is_active: true,
  regions: [],
  sectors: [],
  keywords: [],
  notices: [],
};

interface RenderOptions {
  importedProfile?: CompanyProfileImport | null;
  review?: ReviewStatus;
  blocked?: boolean;
}

function renderStep(defaultValues = {}, options: RenderOptions = {}) {
  const onNext = vi.fn();
  const onImported = vi.fn();
  const onConfirm = vi.fn();
  const onEdit = vi.fn();
  const onClear = vi.fn();
  render(
    <Step1Identity
      defaultValues={defaultValues}
      adminName="Ana Pérez"
      importedProfile={options.importedProfile ?? null}
      onImported={onImported}
      legalNameReview={{ status: options.review, onConfirm, onEdit, onClear }}
      nextBlocked={options.blocked ?? false}
      onNext={onNext}
      onBack={vi.fn()}
    />,
  );
  return { onNext, onImported, onConfirm, onEdit, onClear };
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

describe("Step1Identity (importación por RUT)", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("muestra la tarjeta de importación debajo del RUT", () => {
    renderStep();

    expect(screen.getByRole("button", { name: /importar datos/i })).toBeInTheDocument();
  });

  it("con un RUT inválido muestra el error en el campo y no consulta la fuente", async () => {
    renderStep();

    await userEvent.type(screen.getByLabelText("RUT de la empresa"), "766683040");
    await userEvent.click(screen.getByRole("button", { name: /importar datos/i }));

    expect(
      await screen.findByText("El RUT no es válido. Revisa el dígito verificador."),
    ).toBeInTheDocument();
    expect(importCompanyProfileMock).not.toHaveBeenCalled();
  });

  it("con un 404 de la fuente deja avanzar con Siguiente", async () => {
    importCompanyProfileMock.mockRejectedValue(
      new ApiError(404, "No encontramos datos para el RUT 76668304-5."),
    );
    checkRutExistsMock.mockResolvedValue(false);
    const { onNext, onImported } = renderStep();

    await userEvent.type(
      screen.getByLabelText("Nombre de la empresa"),
      "Constructora Pérez Ltda.",
    );
    await userEvent.type(screen.getByLabelText("RUT de la empresa"), "766683045");
    await userEvent.click(screen.getByRole("button", { name: /importar datos/i }));
    expect(await screen.findByRole("status")).toHaveTextContent(/no encontramos datos/i);
    await userEvent.click(screen.getByRole("button", { name: /Siguiente/ }));

    await waitFor(() => expect(onNext).toHaveBeenCalled());
    expect(importCompanyProfileMock).toHaveBeenCalledWith("76.668.304-5");
    expect(onImported).not.toHaveBeenCalled();
  });
});

describe("Step1Identity (revisión de la razón social)", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  async function importWith(profile: CompanyProfileImport, options: RenderOptions = {}) {
    importCompanyProfileMock.mockResolvedValue(profile);
    const handlers = renderStep({ rut: "76.668.304-5" }, options);
    await userEvent.click(screen.getByRole("button", { name: /importar datos/i }));
    await waitFor(() => expect(handlers.onImported).toHaveBeenCalledWith(profile));
    return handlers;
  }

  it("llena la razón social con lo importado", async () => {
    await importWith(IMPORTED);

    expect(screen.getByLabelText("Nombre de la empresa")).toHaveValue(IMPORTED.legal_name);
  });

  it("reimportar con otro RUT sin razón social vacía el campo", async () => {
    importCompanyProfileMock.mockResolvedValue({ ...IMPORTED, rut: "76086428-5", legal_name: "" });
    const { onImported } = renderStep(
      { rut: "76.086.428-5", legal_name: "Planeta Libre SpA" },
      { importedProfile: IMPORTED, review: "confirmed" },
    );

    await userEvent.click(screen.getByRole("button", { name: /volver a importar/i }));
    await waitFor(() => expect(onImported).toHaveBeenCalled());

    expect(screen.getByLabelText("Nombre de la empresa")).toHaveValue("");
  });

  it("pendiente: el campo es de solo lectura, se ve la insignia y Siguiente está bloqueado", () => {
    renderStep(
      { legal_name: IMPORTED.legal_name },
      { importedProfile: IMPORTED, review: "pending", blocked: true },
    );

    expect(screen.getByLabelText("Nombre de la empresa")).toHaveAttribute("readonly");
    expect(screen.getByText("Pendiente de revisión")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Siguiente/ })).toBeDisabled();
  });

  it("editando: el campo se puede escribir", () => {
    renderStep(
      { legal_name: IMPORTED.legal_name },
      { importedProfile: IMPORTED, review: "editing", blocked: true },
    );

    expect(screen.getByLabelText("Nombre de la empresa")).not.toHaveAttribute("readonly");
  });

  it("confirmar y editar avisan al wizard", async () => {
    const { onConfirm, onEdit } = renderStep(
      { legal_name: IMPORTED.legal_name },
      { importedProfile: IMPORTED, review: "pending", blocked: true },
    );

    await userEvent.click(screen.getByRole("button", { name: "Confirmar razón social" }));
    await userEvent.click(screen.getByRole("button", { name: "Editar razón social" }));

    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onEdit).toHaveBeenCalledTimes(1);
  });

  it("borrar vacía el campo y avisa al wizard", async () => {
    const { onClear } = renderStep(
      { legal_name: IMPORTED.legal_name },
      { importedProfile: IMPORTED, review: "pending", blocked: true },
    );

    await userEvent.click(screen.getByRole("button", { name: "Borrar razón social" }));

    expect(onClear).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText("Nombre de la empresa")).toHaveValue("");
  });

  it("confirmada la razón social, Siguiente avanza", async () => {
    checkRutExistsMock.mockResolvedValue(false);
    const { onNext } = renderStep(
      { legal_name: IMPORTED.legal_name, rut: "76.668.304-5" },
      { importedProfile: IMPORTED, review: "confirmed" },
    );

    await userEvent.click(screen.getByRole("button", { name: /Siguiente/ }));

    await waitFor(() => expect(onNext).toHaveBeenCalled());
  });
});
