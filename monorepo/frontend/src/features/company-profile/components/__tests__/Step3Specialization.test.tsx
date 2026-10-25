import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Step3Specialization } from "../steps/Step3Specialization";
import type { Step3Data } from "../../profileSchema";

const baseValues: Partial<Step3Data> = {
  sectors: ["Construcción"],
  keywords: [],
  certifications: [],
  description: "Constructora especializada en obras civiles menores.",
};

function renderStep(defaultValues: Partial<Step3Data> = baseValues) {
  const onNext = vi.fn();
  render(
    <Step3Specialization defaultValues={defaultValues} onNext={onNext} onBack={vi.fn()} />,
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

