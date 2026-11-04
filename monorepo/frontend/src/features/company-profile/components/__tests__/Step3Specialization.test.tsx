import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Step3Specialization } from "../steps/Step3Specialization";
import type { ReviewStatus } from "../../hooks/useProfileWizard";
import type { Step3Data } from "../../profileSchema";

const suggestMock = vi.hoisted(() => vi.fn());
vi.mock("../../services/supplierService", () => ({
  suggestKeywordsFromDescription: suggestMock,
}));

const baseValues: Partial<Step3Data> = {
  sectors: ["Construcción"],
  keywords: [],
  certifications: [],
  description: "Constructora especializada en obras civiles menores.",
};

// Sin importación: los rubros no están en revisión.
const NO_REVIEW = { status: undefined, onConfirm: vi.fn(), onEdit: vi.fn(), onClear: vi.fn() };

function renderStep(defaultValues: Partial<Step3Data> = baseValues) {
  const onNext = vi.fn();
  render(
    <Step3Specialization
      defaultValues={defaultValues}
      sectorsReview={NO_REVIEW}
      addedSectors={[]}
      nextBlocked={false}
      onNext={onNext}
      onBack={vi.fn()}
    />,
  );
  return { onNext };
}

describe("Step3Specialization (certificaciones)", () => {
  it("envía la certificación con fecha de vencimiento al continuar", async () => {
    const { onNext } = renderStep();

    await userEvent.type(screen.getByLabelText("Nombre de la certificación"), "ISO 9001");
    await userEvent.type(screen.getByLabelText("Fecha de vencimiento"), "2026-12-31");
    await userEvent.click(screen.getByRole("button", { name: "Agregar" }));
    await userEvent.click(screen.getByRole("button", { name: /continuar|siguiente/i }));

    await waitFor(() => expect(onNext).toHaveBeenCalledTimes(1));
    expect(onNext.mock.calls[0][0].certifications).toEqual([
      { name: "ISO 9001", expires_at: "2026-12-31" },
    ]);
  });

  it("muestra las certificaciones iniciales, incluidas las guardadas como string", () => {
    renderStep({
      ...baseValues,
      certifications: ["SEC", { name: "ISO 9001", expires_at: "2026-12-31" }],
    });

    expect(screen.getByText("SEC")).toBeInTheDocument();
    expect(screen.getByText("ISO 9001")).toBeInTheDocument();
    expect(screen.getByText("Vence: 31/12/2026")).toBeInTheDocument();
  });

  it("quita una certificación antes de continuar", async () => {
    const { onNext } = renderStep({
      ...baseValues,
      certifications: [{ name: "ISO 9001", expires_at: "2026-12-31" }],
    });

    await userEvent.click(screen.getByRole("button", { name: "Eliminar ISO 9001" }));
    await userEvent.click(screen.getByRole("button", { name: /continuar|siguiente/i }));

    await waitFor(() => expect(onNext).toHaveBeenCalledTimes(1));
    expect(onNext.mock.calls[0][0].certifications).toEqual([]);
  });
});

describe("Step3Specialization (sugerencias de palabras clave)", () => {
  it("las sugerencias aceptadas pasan a las palabras clave", async () => {
    const onNext = vi.fn();
    render(
      <Step3Specialization
        sectorsReview={NO_REVIEW}
        addedSectors={[]}
        nextBlocked={false}
        defaultValues={baseValues}
        suggestedKeywords={["pintura", "revestimiento"]}
        onNext={onNext}
        onBack={vi.fn()}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Agregar pintura" }));
    await userEvent.click(screen.getByRole("button", { name: /continuar|siguiente/i }));

    await waitFor(() => expect(onNext).toHaveBeenCalledTimes(1));
    expect(onNext.mock.calls[0][0].keywords).toEqual(["pintura"]);
  });

  it("avisa al wizard cuando el usuario descarta una sugerencia", async () => {
    const onDismissKeyword = vi.fn();
    render(
      <Step3Specialization
        sectorsReview={NO_REVIEW}
        addedSectors={[]}
        nextBlocked={false}
        defaultValues={baseValues}
        suggestedKeywords={["pintura"]}
        onDismissKeyword={onDismissKeyword}
        onNext={vi.fn()}
        onBack={vi.fn()}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Descartar pintura" }));

    expect(onDismissKeyword).toHaveBeenCalledWith("pintura");
  });

  it("no muestra las sugerencias que el wizard ya marcó como descartadas", () => {
    render(
      <Step3Specialization
        sectorsReview={NO_REVIEW}
        addedSectors={[]}
        nextBlocked={false}
        defaultValues={baseValues}
        suggestedKeywords={["pintura", "revestimiento"]}
        dismissedKeywords={["pintura"]}
        onDismissKeyword={vi.fn()}
        onNext={vi.fn()}
        onBack={vi.fn()}
      />,
    );

    expect(screen.queryByRole("button", { name: "Agregar pintura" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Agregar revestimiento" })).toBeInTheDocument();
  });
});

describe("Step3Specialization (sugerir desde la descripción)", () => {
  const BUTTON = { name: "Sugerir palabras clave desde la descripción" };

  beforeEach(() => {
    suggestMock.mockReset();
  });

  it("deshabilita el botón mientras la descripción está vacía", () => {
    renderStep({ ...baseValues, description: "" });

    expect(screen.getByRole("button", BUTTON)).toBeDisabled();
  });

  it("deshabilita el botón si la descripción son solo espacios", async () => {
    renderStep({ ...baseValues, description: "" });

    await userEvent.type(screen.getByLabelText(/Descripción de la empresa/), "   ");

    expect(screen.getByRole("button", BUTTON)).toBeDisabled();
  });

  it("envía la descripción y las palabras clave ya elegidas", async () => {
    suggestMock.mockResolvedValue(["obras civiles"]);
    renderStep({ ...baseValues, keywords: ["pintura"] });

    await userEvent.click(screen.getByRole("button", BUTTON));

    await waitFor(() => expect(suggestMock).toHaveBeenCalledTimes(1));
    expect(suggestMock).toHaveBeenCalledWith(baseValues.description, ["pintura"]);
  });

  it("muestra el estado de carga mientras espera la respuesta", async () => {
    let resolve: (keywords: string[]) => void = () => {};
    suggestMock.mockReturnValue(
      new Promise<string[]>((r) => {
        resolve = r;
      }),
    );
    renderStep();

    await userEvent.click(screen.getByRole("button", BUTTON));

    expect(screen.getByRole("button", BUTTON)).toBeDisabled();
    expect(screen.getByRole("button", BUTTON)).toHaveAttribute("aria-busy", "true");

    resolve(["obras civiles"]);
    expect(await screen.findByRole("button", { name: "Agregar obras civiles" })).toBeInTheDocument();
    expect(screen.getByRole("button", BUTTON)).toBeEnabled();
  });

  it("muestra las sugerencias y las aceptadas van a las palabras clave", async () => {
    suggestMock.mockResolvedValue(["obras civiles", "infraestructura municipal"]);
    const { onNext } = renderStep();

    await userEvent.click(screen.getByRole("button", BUTTON));
    await userEvent.click(await screen.findByRole("button", { name: "Agregar obras civiles" }));

    expect(screen.queryByRole("button", { name: "Agregar obras civiles" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /continuar|siguiente/i }));

    await waitFor(() => expect(onNext).toHaveBeenCalledTimes(1));
    expect(onNext.mock.calls[0][0].keywords).toEqual(["obras civiles"]);
  });

  it("descartar una sugerencia la quita y avisa al wizard", async () => {
    suggestMock.mockResolvedValue(["obras civiles", "infraestructura municipal"]);
    const onDismissKeyword = vi.fn();
    render(
      <Step3Specialization
        sectorsReview={NO_REVIEW}
        addedSectors={[]}
        nextBlocked={false}
        defaultValues={baseValues}
        onDismissKeyword={onDismissKeyword}
        onNext={vi.fn()}
        onBack={vi.fn()}
      />,
    );

    await userEvent.click(screen.getByRole("button", BUTTON));
    await userEvent.click(await screen.findByRole("button", { name: "Descartar obras civiles" }));

    expect(screen.queryByRole("button", { name: "Agregar obras civiles" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Agregar infraestructura municipal" })).toBeInTheDocument();
    expect(onDismissKeyword).toHaveBeenCalledWith("obras civiles");
  });

  it("no vuelve a mostrar una sugerencia que el usuario descartó antes", async () => {
    suggestMock.mockResolvedValue(["obras civiles", "infraestructura municipal"]);
    render(
      <Step3Specialization
        sectorsReview={NO_REVIEW}
        addedSectors={[]}
        nextBlocked={false}
        defaultValues={baseValues}
        dismissedKeywords={["Obras Civiles"]}
        onDismissKeyword={vi.fn()}
        onNext={vi.fn()}
        onBack={vi.fn()}
      />,
    );

    await userEvent.click(screen.getByRole("button", BUTTON));

    expect(
      await screen.findByRole("button", { name: "Agregar infraestructura municipal" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Agregar obras civiles" })).not.toBeInTheDocument();
  });

  it("avisa cuando la descripción no da palabras clave nuevas", async () => {
    suggestMock.mockResolvedValue([]);
    renderStep();

    await userEvent.click(screen.getByRole("button", BUTTON));

    expect(await screen.findByText(/No encontramos palabras clave nuevas/)).toBeInTheDocument();
  });

  it("muestra un error legible si la petición falla y deja reintentar", async () => {
    suggestMock.mockRejectedValue(new Error("boom"));
    renderStep();

    await userEvent.click(screen.getByRole("button", BUTTON));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No pudimos sugerir palabras clave. Inténtalo nuevamente o agrégalas a mano.",
    );
    expect(screen.getByRole("button", BUTTON)).toBeEnabled();
  });
});

const REVIEW_DESCRIPTION = "Empresa con amplia experiencia en obras civiles y edificación.";

// Rubros de grupos distintos: el selector arranca con los grupos plegados.
const IMPORTED = "Artículos para estructuras, obras y construcciones";
const MANUAL = "Productos químicos industriales";

async function openSectorGroups() {
  await userEvent.click(screen.getByRole("button", { name: /Componentes y suministros/ }));
  await userEvent.click(screen.getByRole("button", { name: /Materias primas/ }));
}

const chip = (name: string) => screen.getByRole("button", { name });

interface ReviewRenderOptions {
  status?: ReviewStatus;
  blocked?: boolean;
  sectors?: string[];
  added?: string[];
}

function renderReviewStep({
  status,
  blocked = false,
  sectors = [MANUAL, IMPORTED],
  added = [IMPORTED],
}: ReviewRenderOptions = {}) {
  const handlers = {
    onNext: vi.fn(),
    onConfirm: vi.fn(),
    onEdit: vi.fn(),
    onClear: vi.fn(),
  };
  render(
    <Step3Specialization
      defaultValues={{ sectors, description: REVIEW_DESCRIPTION }}
      sectorsReview={{
        status,
        onConfirm: handlers.onConfirm,
        onEdit: handlers.onEdit,
        onClear: handlers.onClear,
      }}
      addedSectors={added}
      nextBlocked={blocked}
      onNext={handlers.onNext}
      onBack={vi.fn()}
    />,
  );
  return handlers;
}


describe("Step3Specialization (revisión de rubros)", () => {
  it("sin importación los rubros se eligen con normalidad y no hay insignia", async () => {
    renderReviewStep({ status: undefined });
    await openSectorGroups();

    expect(chip(IMPORTED)).toBeEnabled();
    expect(screen.queryByText("Pendiente de revisión")).not.toBeInTheDocument();
  });

  it("pendiente: chips deshabilitados, insignia visible y Siguiente bloqueado", async () => {
    renderReviewStep({ status: "pending", blocked: true });
    await openSectorGroups();

    expect(chip(IMPORTED)).toBeDisabled();
    expect(chip(IMPORTED)).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Pendiente de revisión")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Siguiente/ })).toBeDisabled();
  });

  it("editando: los chips se pueden cambiar", async () => {
    renderReviewStep({ status: "editing", blocked: true });
    await openSectorGroups();

    await userEvent.click(chip(IMPORTED));

    expect(chip(IMPORTED)).toHaveAttribute("aria-pressed", "false");
  });

  it("confirmar y editar avisan al wizard", async () => {
    const { onConfirm, onEdit } = renderReviewStep({ status: "pending", blocked: true });
    await openSectorGroups();

    await userEvent.click(screen.getByRole("button", { name: "Confirmar rubros" }));
    await userEvent.click(screen.getByRole("button", { name: "Editar rubros" }));

    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onEdit).toHaveBeenCalledTimes(1);
  });

  it("borrar quita solo los rubros que trajo la importación", async () => {
    const { onClear } = renderReviewStep({ status: "pending", blocked: true });
    await openSectorGroups();

    await userEvent.click(screen.getByRole("button", { name: "Borrar rubros" }));

    expect(onClear).toHaveBeenCalledTimes(1);
    expect(chip(IMPORTED)).toHaveAttribute("aria-pressed", "false");
    expect(chip(MANUAL)).toHaveAttribute("aria-pressed", "true");
  });

  it("confirmados los rubros, Siguiente avanza", async () => {
    const { onNext } = renderReviewStep({ status: "confirmed" });
    await openSectorGroups();

    await userEvent.click(screen.getByRole("button", { name: /Siguiente/ }));

    await vi.waitFor(() => expect(onNext).toHaveBeenCalled());
  });
});
