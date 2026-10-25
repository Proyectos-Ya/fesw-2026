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
