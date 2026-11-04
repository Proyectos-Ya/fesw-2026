import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Step2Operations } from "../steps/Step2Operations";
import type { ReviewStatus } from "../../hooks/useProfileWizard";

interface RenderOptions {
  status?: ReviewStatus;
  blocked?: boolean;
  regions?: string[];
  added?: string[];
}

function renderStep({
  status,
  blocked = false,
  regions = ["Valparaíso", "Metropolitana"],
  added = ["Metropolitana"],
}: RenderOptions = {}) {
  const handlers = {
    onNext: vi.fn(),
    onConfirm: vi.fn(),
    onEdit: vi.fn(),
    onClear: vi.fn(),
  };
  render(
    <Step2Operations
      defaultValues={{ regions, years_experience: 5, num_employees: 12 }}
      regionsReview={{
        status,
        onConfirm: handlers.onConfirm,
        onEdit: handlers.onEdit,
        onClear: handlers.onClear,
      }}
      addedRegions={added}
      nextBlocked={blocked}
      onNext={handlers.onNext}
      onBack={vi.fn()}
    />,
  );
  return handlers;
}

const chip = (name: string) => screen.getByRole("button", { name });

describe("Step2Operations (revisión de regiones)", () => {
  it("ya no ofrece importar datos en este paso", () => {
    renderStep();

    expect(screen.queryByRole("button", { name: /importar datos/i })).not.toBeInTheDocument();
  });

  it("sin importación las regiones se eligen con normalidad y no hay insignia", async () => {
    renderStep({ status: undefined });

    await userEvent.click(chip("Ñuble"));

    expect(chip("Ñuble")).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByText("Pendiente de revisión")).not.toBeInTheDocument();
  });

  it("pendiente: chips deshabilitados, insignia visible y Siguiente bloqueado", () => {
    renderStep({ status: "pending", blocked: true });

    expect(chip("Ñuble")).toBeDisabled();
    expect(chip("Metropolitana")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Pendiente de revisión")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Siguiente/ })).toBeDisabled();
  });

  it("editando: los chips se pueden cambiar", async () => {
    renderStep({ status: "editing", blocked: true });

    await userEvent.click(chip("Ñuble"));

    expect(chip("Ñuble")).toHaveAttribute("aria-pressed", "true");
  });

  it("confirmar y editar avisan al wizard", async () => {
    const { onConfirm, onEdit } = renderStep({ status: "pending", blocked: true });

    await userEvent.click(screen.getByRole("button", { name: "Confirmar regiones" }));
    await userEvent.click(screen.getByRole("button", { name: "Editar regiones" }));

    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onEdit).toHaveBeenCalledTimes(1);
  });

  it("borrar quita solo las regiones que trajo la importación", async () => {
    const { onClear } = renderStep({ status: "pending", blocked: true });

    await userEvent.click(screen.getByRole("button", { name: "Borrar regiones" }));

    expect(onClear).toHaveBeenCalledTimes(1);
    expect(chip("Metropolitana")).toHaveAttribute("aria-pressed", "false");
    expect(chip("Valparaíso")).toHaveAttribute("aria-pressed", "true");
  });

  it("confirmadas las regiones, Siguiente avanza", async () => {
    const { onNext } = renderStep({ status: "confirmed" });

    await userEvent.click(screen.getByRole("button", { name: /Siguiente/ }));

    await vi.waitFor(() => expect(onNext).toHaveBeenCalled());
  });
});
