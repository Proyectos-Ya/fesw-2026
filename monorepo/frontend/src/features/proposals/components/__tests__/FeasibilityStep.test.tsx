import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { FeasibilityStep } from "../FeasibilityStep";
import { SEC, SEC_NEGATIVA, VIALES, requisito, respuesta, vista } from "../../testing/fixtures";

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

  it("si las bases no lo mencionan, lo presenta como opcional con el motivo", () => {
    renderStep({
      requires_technical_document: false,
      technical_document_reason: "La ficha menciona un TDR que no se recibió.",
    });

    expect(screen.getByText(/Documento técnico: opcional\./)).toBeInTheDocument();
    expect(screen.getByText(/TDR que no se recibió/)).toBeInTheDocument();
    expect(screen.queryByText(/No se exige/)).not.toBeInTheDocument();
  });

  it("dice cuando las bases piden documento técnico", () => {
    renderStep({
      requires_technical_document: true,
      technical_document_reason: "El punto 4 pide una propuesta técnica.",
    });

    expect(screen.getByText(/Las bases piden un documento técnico\./)).toBeInTheDocument();
    expect(screen.getByText(/El punto 4 pide una propuesta técnica/)).toBeInTheDocument();
  });

  it("dice cuando las bases lo mencionan sin indicar si va con la cotización", () => {
    renderStep({
      requires_technical_document: false,
      technical_document_ambiguous: true,
      technical_document_reason: 'Las bases dicen "Se debe entregar informe técnico".',
    });

    expect(
      screen.getByText(
        /Las bases mencionan un documento técnico, pero no indican si va con la cotización\./,
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/Se debe entregar informe técnico/)).toBeInTheDocument();
    expect(screen.queryByText(/No se exige/)).not.toBeInTheDocument();
  });
});

describe("FeasibilityStep: cambiar una respuesta ya dada", () => {
  const evaluada = (overrides = {}) => ({
    requirements: [requisito({ status: "cumple" })],
    catalog_items: [respuesta(SEC, "Sí")],
    ...overrides,
  });

  it("despliega las opciones, marca la actual y responde", async () => {
    const { onAnswer } = renderStep(evaluada());

    const lista = screen.getByRole("region", { name: "Exigencias evaluadas" });
    await userEvent.click(within(lista).getByRole("button", { name: "Cambiar respuesta" }));

    expect(within(lista).getByRole("button", { name: "Sí" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(within(lista).getByRole("button", { name: "No" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    await userEvent.click(within(lista).getByRole("button", { name: "No" }));

    expect(onAnswer).toHaveBeenCalledWith(SEC.id, "No");
  });

  it("si la respuesta vino de otra licitación avisa que el cambio aplica a todas", async () => {
    renderStep(
      evaluada({
        requirements: [requisito({ status: "no_cumple", mandatory: false })],
        catalog_items: [SEC_NEGATIVA],
      }),
    );

    await userEvent.click(screen.getByRole("button", { name: "Cambiar respuesta" }));

    expect(
      screen.getByText(
        /Respondida el .+ en otra licitación\. Cambiarla la actualiza para todas tus postulaciones\./,
      ),
    ).toBeInTheDocument();
  });

  it("si la respuesta es de esta licitación no avisa", async () => {
    renderStep(evaluada());

    await userEvent.click(screen.getByRole("button", { name: "Cambiar respuesta" }));

    expect(screen.queryByText(/en otra licitación/)).not.toBeInTheDocument();
  });

  it("con el borrador listo también se puede cambiar", () => {
    renderStep(evaluada({ status: "READY" }));

    expect(screen.getByRole("button", { name: "Cambiar respuesta" })).toBeEnabled();
  });

  it.each([
    ["en pausa", { status: "PAUSED" }, {}],
    ["detenida", { status: "STOPPED" }, {}],
    ["vencida", { is_expired: true }, {}],
    ["sin permiso", {}, { canWrite: false }],
  ])("%s no se ofrece", (_caso, overrides, props) => {
    renderStep(evaluada(overrides), props);

    expect(screen.queryByRole("button", { name: "Cambiar respuesta" })).not.toBeInTheDocument();
  });

  it("una exigencia que no viene de una pregunta no se cambia", () => {
    renderStep(
      evaluada({
        requirements: [requisito({ status: "cumple", capability_question_id: null })],
      }),
    );

    expect(screen.queryByRole("button", { name: "Cambiar respuesta" })).not.toBeInTheDocument();
  });

  it("mientras se guarda, el botón pulsado carga y los demás esperan", async () => {
    renderStep(evaluada(), { busy: true, answering: { questionId: SEC.id, label: "No" } });

    await userEvent.click(screen.getByRole("button", { name: "Cambiar respuesta" }));

    expect(screen.getByRole("button", { name: "No" })).toHaveAttribute("aria-busy", "true");
    expect(screen.getByRole("button", { name: "Sí" })).toBeDisabled();
  });
});

describe("FeasibilityStep: proyectos de experiencia", () => {
  const conViales = (overrides = {}) => ({
    requirements: [
      requisito({
        id: "req-2",
        text: "Se valorará experiencia en obras viales.",
        kind: "experiencia",
        mandatory: false,
        status: "cumple",
        capability_question_id: VIALES.id,
      }),
    ],
    catalog_items: [respuesta(VIALES, "Sí")],
    ...overrides,
  });

  it("con un Sí vigente ofrece agregar un proyecto y lo guarda", async () => {
    const onAddEvidence = vi.fn().mockResolvedValue(undefined);
    renderStep(conViales(), { onAddEvidence });

    const lista = screen.getByRole("region", { name: "Exigencias evaluadas" });
    await userEvent.click(within(lista).getByRole("button", { name: "Agregar proyecto" }));
    await userEvent.type(screen.getByLabelText("Título del proyecto"), "Bacheo");
    await userEvent.type(screen.getByLabelText("Mandante"), "Serviu");
    await userEvent.type(screen.getByLabelText("Año"), "2023");
    await userEvent.click(screen.getByRole("button", { name: "Guardar proyecto" }));

    expect(onAddEvidence).toHaveBeenCalledWith(
      VIALES.id,
      expect.objectContaining({ title: "Bacheo", year: 2023 }),
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("con un No, en otra clase de pregunta o sin permiso no se ofrece", () => {
    const onAddEvidence = vi.fn();
    const { unmount } = render(
      <FeasibilityStep
        view={vista(conViales({ catalog_items: [respuesta(VIALES, "No")] }))}
        canWrite
        busy={false}
        onAnswer={vi.fn()}
        onGenerate={vi.fn()}
        onAddEvidence={onAddEvidence}
      />,
    );
    expect(screen.queryByRole("button", { name: "Agregar proyecto" })).not.toBeInTheDocument();
    unmount();

    renderStep(
      { requirements: [requisito({ status: "cumple" })], catalog_items: [respuesta(SEC, "Sí")] },
      { onAddEvidence },
    );
    expect(screen.queryByRole("button", { name: "Agregar proyecto" })).not.toBeInTheDocument();
  });

  it("sin permiso no se ofrece", () => {
    renderStep(conViales(), { canWrite: false, onAddEvidence: vi.fn() });

    expect(screen.queryByRole("button", { name: "Agregar proyecto" })).not.toBeInTheDocument();
  });

  it("justo después de un Sí sugiere agregar el proyecto, sin obligar", async () => {
    const onDismissEvidence = vi.fn();
    renderStep(conViales(), {
      onAddEvidence: vi.fn(),
      suggestedEvidence: VIALES.id,
      onDismissEvidence,
    });

    const aviso = screen.getByRole("status", { name: "Agregar un proyecto" });
    expect(aviso).toHaveTextContent(VIALES.question);
    await userEvent.click(within(aviso).getByRole("button", { name: "Ahora no" }));
    expect(onDismissEvidence).toHaveBeenCalled();

    await userEvent.click(within(aviso).getByRole("button", { name: "Agregar proyecto" }));
    expect(screen.getByRole("dialog", { name: "Agregar proyecto" })).toBeInTheDocument();
  });

  it("sin permiso no sugiere", () => {
    renderStep(conViales(), {
      canWrite: false,
      onAddEvidence: vi.fn(),
      suggestedEvidence: VIALES.id,
    });

    expect(screen.queryByRole("status", { name: "Agregar un proyecto" })).not.toBeInTheDocument();
  });
});
