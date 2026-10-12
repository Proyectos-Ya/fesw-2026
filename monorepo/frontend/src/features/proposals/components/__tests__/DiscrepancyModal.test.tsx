import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DiscrepancyModal } from "../DiscrepancyModal";
import { SEC, SEC_NEGATIVA, requisito, vista } from "../../testing/fixtures";

const pausada = (overrides = {}) =>
  vista({
    status: "PAUSED",
    paused_requirement_id: "req-1",
    requirements: [requisito({ status: "no_cumple" })],
    ...overrides,
  });

function renderModal(view = pausada(), canWrite = true) {
  const onUpdateAnswer = vi.fn();
  const onDecide = vi.fn();
  render(
    <DiscrepancyModal
      view={view}
      open
      busy={false}
      canWrite={canWrite}
      onClose={vi.fn()}
      onUpdateAnswer={onUpdateAnswer}
      onDecide={onDecide}
    />,
  );
  return { onUpdateAnswer, onDecide };
}

describe("DiscrepancyModal (CA7, CA8, CA9)", () => {
  it("muestra la exigencia y la recomendación", () => {
    renderModal();

    expect(screen.getByRole("dialog")).toHaveTextContent(
      "Deberá contar con certificación SEC.",
    );
    expect(screen.getByText(/Recomendamos no postular/)).toBeInTheDocument();
  });

  it("continuar con advertencia (CA8)", async () => {
    const { onDecide } = renderModal();

    await userEvent.click(screen.getByRole("button", { name: "Continuar con advertencia" }));

    expect(onDecide).toHaveBeenCalledWith("req-1", "continue");
  });

  it("detener (CA9)", async () => {
    const { onDecide } = renderModal();

    await userEvent.click(screen.getByRole("button", { name: "Detener postulación" }));

    expect(onDecide).toHaveBeenCalledWith("req-1", "stop");
  });

  it("actualizar la respuesta ofrece solo las opciones que no son No", async () => {
    const { onUpdateAnswer } = renderModal();

    expect(screen.queryByRole("button", { name: "No" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Sí" }));

    expect(onUpdateAnswer).toHaveBeenCalledWith(SEC.id, "Sí");
  });

  it("explica que el No viene de otra licitación", () => {
    renderModal(
      pausada({
        requirements: [requisito({ status: "no_cumple", catalog_item_id: SEC_NEGATIVA.id })],
        catalog_items: [SEC_NEGATIVA],
      }),
    );

    expect(screen.getByText(/respondió "No" el .* en otra licitación/)).toBeInTheDocument();
  });

  it("sin permiso no deja decidir", () => {
    renderModal(pausada(), false);

    expect(
      screen.queryByRole("button", { name: "Continuar con advertencia" }),
    ).not.toBeInTheDocument();
  });

  it("sin pausa no se muestra", () => {
    renderModal(vista());

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
