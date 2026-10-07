import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { FeasibilityStep } from "../FeasibilityStep";
import { SEC, VIALES, requisito, vista } from "../../testing/fixtures";

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

  it("una pregunta sugerida dice que es para fortalecer la oferta", () => {
    renderStep({
      requirements: [
        requisito({
          id: "sug-1",
          text: "Entrega en la comuna de Pica",
          kind: "disponibilidad",
          mandatory: false,
          suggested: true,
        }),
      ],
    });

    expect(screen.getByText(/Sugerida para fortalecer tu oferta/)).toBeInTheDocument();
    expect(screen.queryByText(/Las bases dicen/)).not.toBeInTheDocument();
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

  it("en pausa, las pendientes explican por qué no se pueden responder", () => {
    renderStep({
      status: "PAUSED",
      paused_requirement_id: "req-1",
      requirements: [
        requisito({ status: "no_cumple" }),
        requisito({ id: "req-2", capability_question_id: VIALES.id, mandatory: false }),
      ],
    });

    const pendientes = screen.getByRole("region", { name: /Preguntas por responder/ });
    expect(pendientes).toHaveTextContent(/cuando resuelvas la exigencia excluyente/);
    for (const boton of within(pendientes).getAllByRole("button")) {
      expect(boton).toBeDisabled();
    }
  });

  it("detenida, las pendientes dicen que hay que reanudar", () => {
    renderStep({ status: "STOPPED" });

    expect(
      screen.getByRole("region", { name: /Preguntas por responder/ }),
    ).toHaveTextContent(/Reanúdala para responder/);
  });

  it("tras reanudar, la exigencia que la detuvo se puede responder de nuevo", async () => {
    const { onAnswer } = renderStep({
      requirements: [requisito({ status: "no_cumple" })],
      discrepancy_decisions: [
        {
          requirement_id: "req-1",
          capability_question_id: SEC.id,
          action: "stop",
          user_id: "u-1",
          decided_at: "2026-10-01T12:00:00Z",
        },
      ],
    });

    const deNuevo = screen.getByRole("region", { name: /Responder de nuevo/ });
    expect(within(deNuevo).getByText(SEC.question)).toBeInTheDocument();
    expect(deNuevo).toHaveTextContent(/vuelve a quedar en pausa/);
    expect(screen.queryByText("Exigencias evaluadas")).not.toBeInTheDocument();

    await userEvent.click(within(deNuevo).getByRole("button", { name: "Sí" }));

    expect(onAnswer).toHaveBeenCalledWith(SEC.id, "Sí");
  });

  it("el botón pulsado muestra que está cargando", () => {
    renderStep({}, { busy: true, answering: { questionId: SEC.id, label: "Sí" } });

    const pendientes = screen.getByRole("region", { name: /Preguntas por responder/ });
    const [si] = within(pendientes).getAllByRole("button", { name: "Sí" });
    const [no] = within(pendientes).getAllByRole("button", { name: "No" });
    expect(si).toHaveAttribute("aria-busy", "true");
    expect(no).not.toHaveAttribute("aria-busy", "true");
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
