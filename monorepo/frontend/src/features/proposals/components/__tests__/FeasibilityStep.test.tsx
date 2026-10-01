import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { FeasibilityStep } from "../FeasibilityStep";
import { SEC, requisito, vista } from "../../testing/fixtures";

function renderStep(overrides = {}, props = {}) {
  const onAnswer = vi.fn();
  const onGenerate = vi.fn();
  render(
    <FeasibilityStep
      view={vista(overrides)}
      canWrite
      busy={false}
      onAnswer={onAnswer}
      onGenerate={onGenerate}
      {...props}
    />,
  );
  return { onAnswer, onGenerate };
}

describe("FeasibilityStep", () => {
  it("muestra cada pregunta pendiente con sus opciones y responde", async () => {
    const { onAnswer } = renderStep();

    const pendientes = screen.getByRole("region", { name: /Preguntas por responder \(2\)/ });
    expect(within(pendientes).getByText(SEC.question)).toBeInTheDocument();

    await userEvent.click(within(pendientes).getAllByRole("button", { name: "No" })[0]);

    expect(onAnswer).toHaveBeenCalledWith(SEC.id, "No");
  });

  it("las condiciones del servicio se muestran sin preguntarlas", () => {
    renderStep();

    expect(screen.getByText("Condiciones del servicio")).toBeInTheDocument();
    expect(screen.getByText("Duración de 40 horas")).toBeInTheDocument();
  });

  it("con preguntas pendientes no deja redactar", () => {
    renderStep();

    expect(screen.getByRole("button", { name: /Redactar borrador/ })).toBeDisabled();
    expect(screen.getByText(/Responde las preguntas pendientes/)).toBeInTheDocument();
  });

  it("con todo respondido deja redactar", async () => {
    const { onGenerate } = renderStep({
      requirements: [requisito({ status: "cumple" })],
    });

    await userEvent.click(screen.getByRole("button", { name: /Redactar borrador/ }));

    expect(onGenerate).toHaveBeenCalled();
  });

  it("sin permiso no hay botones de acción", () => {
    renderStep({}, { canWrite: false });

    expect(screen.queryByRole("button", { name: /Redactar borrador/ })).not.toBeInTheDocument();
    for (const boton of screen.getAllByRole("button", { name: "Sí" })) {
      expect(boton).toBeDisabled();
    }
  });

  it("explica por qué se exige (o no) documento técnico", () => {
    renderStep({
      requires_technical_document: false,
      technical_document_reason: "La ficha menciona un TDR que no se recibió.",
    });

    expect(screen.getByText(/No se exige documento técnico/)).toBeInTheDocument();
    expect(screen.getByText(/TDR que no se recibió/)).toBeInTheDocument();
  });
});
