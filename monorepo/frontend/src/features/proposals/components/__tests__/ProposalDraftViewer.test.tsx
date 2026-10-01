import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProposalDraftViewer } from "../ProposalDraftViewer";
import { vista } from "../../testing/fixtures";
import type { DraftContent, ProposalView } from "../../types";

const CONTENIDO: DraftContent = {
  offer_name: { paragraphs: [{ text: "Capacitación PAC", sources: [], placeholders: [] }] },
  offer_description: {
    paragraphs: [
      {
        text: "Operamos en Aysén hace 8 años.",
        sources: [{ id: "perfil:region:aysen", label: "Región de operación: Aysén" }],
        placeholders: [],
      },
      {
        text: "Relator: (Por favor, inserte aquí el valor nombre del relator).",
        sources: [],
        placeholders: ["nombre del relator"],
      },
    ],
  },
  required_documents: {
    paragraphs: [{ text: "Adjuntar cotización", sources: [], placeholders: [] }],
  },
  technical_document: null,
};

function listo(overrides: Partial<ProposalView> = {}): ProposalView {
  return vista({ status: "READY", content: CONTENIDO, ...overrides });
}

function renderViewer(view = listo(), canWrite = true) {
  const onRegenerate = vi.fn();
  const onDownload = vi.fn();
  render(
    <ProposalDraftViewer
      view={view}
      canWrite={canWrite}
      busy={false}
      onRegenerate={onRegenerate}
      onDownload={onDownload}
    />,
  );
  return { onRegenerate, onDownload };
}

beforeEach(() => {
  Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });
});

describe("ProposalDraftViewer", () => {
  it("muestra nombre, descripción y documentos (CA1)", () => {
    renderViewer();

    expect(screen.getByRole("region", { name: "Nombre de la oferta" })).toHaveTextContent(
      "Capacitación PAC",
    );
    expect(
      screen.getByRole("region", { name: "Documentos necesarios" }),
    ).toHaveTextContent("Adjuntar cotización");
  });

  it("copia una sección para pegarla en el formulario", async () => {
    renderViewer();

    await userEvent.click(screen.getByRole("button", { name: "Copiar nombre de la oferta" }));

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("Capacitación PAC");
  });

  it("al elegir un párrafo muestra sus fuentes (CA5)", async () => {
    renderViewer();

    await userEvent.click(screen.getByRole("button", { name: /Operamos en Aysén/ }));

    expect(screen.getByRole("complementary", { name: "Fuentes del párrafo" })).toHaveTextContent(
      "Región de operación: Aysén",
    );
  });

  it("un párrafo con vacíos dice qué completar (CA2)", async () => {
    renderViewer();

    await userEvent.click(screen.getByRole("button", { name: /Relator:/ }));

    const panel = screen.getByRole("complementary", { name: "Fuentes del párrafo" });
    expect(panel).toHaveTextContent("no cita datos de la empresa");
    expect(panel).toHaveTextContent("Falta completar: nombre del relator.");
  });

  it("muestra las advertencias aceptadas", () => {
    renderViewer(
      listo({
        warnings: [{ requirement_id: "req-1", text: "Las bases exigen SEC. No se cumple." }],
      }),
    );

    expect(screen.getByRole("alert")).toHaveTextContent("Las bases exigen SEC.");
  });

  it("regenera con instrucciones (CA4)", async () => {
    const { onRegenerate } = renderViewer();

    await userEvent.click(screen.getByRole("button", { name: /Regenerar/ }));
    const dialogo = screen.getByRole("dialog");
    await userEvent.type(within(dialogo).getByRole("textbox"), "Tono más formal");
    await userEvent.click(within(dialogo).getByRole("button", { name: "Regenerar" }));

    expect(onRegenerate).toHaveBeenCalledWith("Tono más formal");
  });

  it("sin documento técnico no hay botón de exportar (CA3)", () => {
    renderViewer();

    expect(screen.queryByRole("button", { name: /Exportar a .docx/ })).not.toBeInTheDocument();
  });

  it("con documento técnico lo muestra y deja exportarlo (CA3)", async () => {
    const { onDownload } = renderViewer(
      listo({
        content: {
          ...CONTENIDO,
          technical_document: {
            sections: [
              {
                key: "metodologia",
                title: "Metodología",
                paragraphs: [{ text: "Clases presenciales.", sources: [], placeholders: [] }],
              },
            ],
          },
        },
      }),
    );

    expect(screen.getByRole("region", { name: "Documento técnico" })).toHaveTextContent(
      "Clases presenciales.",
    );
    await userEvent.click(screen.getByRole("button", { name: /Exportar a .docx/ }));
    expect(onDownload).toHaveBeenCalled();
  });

  it("sin permiso no deja regenerar", () => {
    renderViewer(listo(), false);

    expect(screen.queryByRole("button", { name: /Regenerar/ })).not.toBeInTheDocument();
  });
});
