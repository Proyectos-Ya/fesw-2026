import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProposalDraftViewer } from "../ProposalDraftViewer";
import { vista } from "../../testing/fixtures";
import { MAX_DETALLE_COTIZACION } from "../../utils/proposal";
import type { DraftContent, ProposalStage, ProposalView } from "../../types";

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

function renderViewer(view = listo(), canWrite = true, stage: ProposalStage = null) {
  const onRegenerate = vi.fn();
  const onDownload = vi.fn();
  const onRequestTechnical = vi.fn();
  render(
    <ProposalDraftViewer
      view={view}
      canWrite={canWrite}
      busy={stage !== null}
      stage={stage}
      onRegenerate={onRegenerate}
      onDownload={onDownload}
      onRequestTechnical={onRequestTechnical}
    />,
  );
  return { onRegenerate, onDownload, onRequestTechnical };
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

  it("sin documento técnico avisa que no se detectó y no deja exportar (CA3)", () => {
    renderViewer(
      listo({ technical_document_reason: "La ficha solo pide una cotización." }),
    );

    const bloque = screen.getByRole("region", { name: "Documento técnico" });
    expect(bloque).toHaveTextContent(
      "No se detectó que esta licitación pida un documento técnico",
    );
    expect(bloque).toHaveTextContent("La ficha solo pide una cotización.");
    expect(screen.queryByRole("button", { name: /Exportar a .docx/ })).not.toBeInTheDocument();
  });

  it("se puede generar el documento técnico de todas formas", async () => {
    const { onRequestTechnical } = renderViewer();

    await userEvent.click(screen.getByRole("button", { name: /Generar de todas formas/ }));

    expect(onRequestTechnical).toHaveBeenCalled();
  });

  it("sin permiso no ofrece generarlo", () => {
    renderViewer(listo(), false);

    expect(
      screen.queryByRole("button", { name: /Generar de todas formas/ }),
    ).not.toBeInTheDocument();
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

  it("al regenerar cubre el borrador con una capa de carga y el botón carga", () => {
    renderViewer(listo(), true, "regenerating");

    expect(screen.getByTestId("capa-de-carga")).toBeInTheDocument();
    expect(screen.getByTestId("contenido-borrador")).toHaveAttribute("aria-busy", "true");
    expect(screen.getByRole("button", { name: /Regenerar/ })).toHaveAttribute(
      "aria-busy",
      "true",
    );
  });

  it("al redactar también muestra la capa de carga", () => {
    renderViewer(listo(), true, "drafting");

    expect(screen.getByTestId("capa-de-carga")).toBeInTheDocument();
  });

  it("sin etapa en curso no hay capa de carga", () => {
    renderViewer();

    expect(screen.queryByTestId("capa-de-carga")).not.toBeInTheDocument();
  });

  it("sin permiso no deja regenerar", () => {
    renderViewer(listo(), false);

    expect(screen.queryByRole("button", { name: /Regenerar/ })).not.toBeInTheDocument();
  });
  describe("detalle de la cotización", () => {
    const detalle = (texto: string) =>
      listo({
        content: {
          ...CONTENIDO,
          offer_description: { paragraphs: [{ text: texto, sources: [], placeholders: [] }] },
        },
      });

    it("se rotula como en Mercado Público y cuenta los caracteres que se copian", () => {
      renderViewer();

      const seccion = screen.getByRole("region", { name: "Detalle de la cotización" });
      const copiado = CONTENIDO.offer_description.paragraphs.map((p) => p.text).join("\n\n");
      expect(seccion).toHaveTextContent(`${copiado.length}/255`);
      expect(screen.queryByText(/Supera los 255/)).not.toBeInTheDocument();
      expect(screen.queryByRole("region", { name: "Descripción de la oferta" })).toBeNull();
    });

    it("con 255 caracteres justos no avisa", () => {
      renderViewer(detalle("a".repeat(MAX_DETALLE_COTIZACION)));

      expect(screen.getByText("255/255")).not.toHaveClass("text-danger");
      expect(screen.queryByText(/Supera los 255/)).not.toBeInTheDocument();
    });

    it("sobre 255 caracteres lo marca y sugiere acortarlo o regenerar", () => {
      renderViewer(detalle("a".repeat(300)));

      expect(screen.getByText("300/255")).toHaveClass("text-danger");
      expect(
        screen.getByText(
          "Supera los 255 caracteres que acepta Mercado Público. Acórtalo antes de pegarlo, o regenera pidiendo un texto más corto.",
        ),
      ).toBeInTheDocument();
    });

    it("se copia con su propio botón", async () => {
      renderViewer(detalle("Servicio de bacheo para Pica."));

      await userEvent.click(
        screen.getByRole("button", { name: "Copiar detalle de la cotización" }),
      );

      expect(navigator.clipboard.writeText).toHaveBeenCalledWith("Servicio de bacheo para Pica.");
    });
  });
});
