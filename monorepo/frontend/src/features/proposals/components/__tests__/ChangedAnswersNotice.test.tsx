import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ChangedAnswersNotice } from "../ChangedAnswersNotice";
import { SEC, SEC_NEGATIVA, vista } from "../../testing/fixtures";
import type { DraftContent } from "../../types";

const contenido: DraftContent = {
  offer_name: { paragraphs: [] },
  offer_description: { paragraphs: [] },
  required_documents: { paragraphs: [] },
  technical_document: null,
};

describe("ChangedAnswersNotice", () => {
  it("sin respuestas cambiadas no muestra nada", () => {
    const { container } = render(
      <ChangedAnswersNotice view={vista()} canWrite busy={false} onSync={vi.fn()} />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("muestra la pregunta y la respuesta vigente de cada exigencia afectada", () => {
    render(
      <ChangedAnswersNotice
        view={vista({ changed_requirement_ids: ["req-1"], catalog_items: [SEC_NEGATIVA] })}
        canWrite
        busy={false}
        onSync={vi.fn()}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent(SEC.question);
    expect(screen.getByRole("status")).toHaveTextContent("ahora: No");
  });

  it("avisa cuando la respuesta ya no está vigente", () => {
    render(
      <ChangedAnswersNotice
        view={vista({ changed_requirement_ids: ["req-1"] })}
        canWrite
        busy={false}
        onSync={vi.fn()}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent("sin respuesta vigente");
  });

  it("con borrador redactado ofrece actualizarlo", () => {
    const onSync = vi.fn();
    render(
      <ChangedAnswersNotice
        view={vista({ status: "READY", content: contenido, changed_requirement_ids: ["req-1"] })}
        canWrite
        busy={false}
        onSync={onSync}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Actualizar borrador" }));

    expect(onSync).toHaveBeenCalled();
  });

  it("sin borrador redactado ofrece aplicar las respuestas", () => {
    render(
      <ChangedAnswersNotice
        view={vista({ changed_requirement_ids: ["req-1"] })}
        canWrite
        busy={false}
        onSync={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Aplicar las respuestas" })).toBeInTheDocument();
  });

  it("sin permiso avisa pero no ofrece la acción", () => {
    render(
      <ChangedAnswersNotice
        view={vista({ changed_requirement_ids: ["req-1"] })}
        canWrite={false}
        busy={false}
        onSync={vi.fn()}
      />,
    );

    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
