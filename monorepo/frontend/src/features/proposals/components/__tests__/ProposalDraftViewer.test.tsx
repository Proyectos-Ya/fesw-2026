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

  it("explica cómo ver las fuentes de cada párrafo", () => {
    renderViewer();

    expect(screen.getByText(/pasa el cursor o toca .Fuentes. en cada párrafo/i)).toBeInTheDocument();
  });

  it("al pasar el cursor por las fuentes de un párrafo las muestra a su lado (CA5)", async () => {
    renderViewer();

    await userEvent.hover(screen.getByRole("button", { name: /Fuentes del párrafo: Operamos en Aysén/ }));

    expect(screen.getByRole("tooltip")).toHaveTextContent("Región de operación: Aysén");
  });

  it("al dejar de pasar el cursor las oculta", async () => {
    renderViewer();
    const boton = screen.getByRole("button", { name: /Fuentes del párrafo: Operamos en Aysén/ });

    await userEvent.hover(boton);
    await userEvent.unhover(boton);

    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("en el celular se abre al tocar y se cierra con Escape", async () => {
    renderViewer();
    const boton = screen.getByRole("button", { name: /Fuentes del párrafo: Operamos en Aysén/ });

    await userEvent.click(boton);
    expect(boton).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("tooltip")).toHaveTextContent("Región de operación: Aysén");

    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("indica cuántas fuentes tiene cada párrafo", () => {
    renderViewer();

    expect(
      screen.getByRole("button", { name: /Fuentes del párrafo: Operamos en Aysén/ }),
    ).toHaveTextContent("1");
  });

  it("un párrafo con vacíos dice qué completar (CA2)", async () => {
    renderViewer();

    await userEvent.hover(screen.getByRole("button", { name: /Fuentes del párrafo: Relator:/ }));

    const globo = screen.getByRole("tooltip");
    expect(globo).toHaveTextContent("no cita datos de la empresa");
    expect(globo).toHaveTextContent("Falta completar: nombre del relator.");
  });

  it("ya no hay un panel de fuentes aparte", () => {
    renderViewer();

    expect(screen.queryByRole("complementary", { name: "Fuentes del párrafo" })).not.toBeInTheDocument();
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

  it("si las bases no lo solicitan, lo dice y lo ofrece como opcional (CA3)", () => {
    renderViewer(listo({ technical_document_reason: "Las bases no solicitan un informe técnico." }));

    const bloque = screen.getByRole("region", { name: "Documento técnico" });
    expect(bloque).toHaveTextContent("Documento técnico (opcional)");
    expect(bloque).toHaveTextContent("Las bases no solicitan un informe técnico.");
    expect(bloque).toHaveTextContent(
      "Un documento técnico breve que describa tu servicio puede reforzar la oferta.",
    );
    expect(screen.queryByRole("button", { name: /Exportar a .docx/ })).not.toBeInTheDocument();
  });

  it("no da un veredicto ni usa tono de advertencia", () => {
    renderViewer(listo({ technical_document_reason: "Las bases no solicitan un informe técnico." }));

    const bloque = screen.getByRole("region", { name: "Documento técnico" });
    expect(bloque).not.toHaveTextContent("No se detectó");
    expect(bloque).not.toHaveTextContent("No se exige");
    expect(bloque.className).not.toMatch(/warning/);
  });

  it("se puede generar aunque las bases no lo soliciten", async () => {
    const { onRequestTechnical } = renderViewer();

    const boton = screen.getByRole("button", { name: /Generar documento técnico/ });
    expect(boton).not.toHaveClass("bg-primary");
    await userEvent.click(boton);

    expect(onRequestTechnical).toHaveBeenCalled();
  });

  it("sin permiso no ofrece generarlo", () => {
    renderViewer(listo(), false);

    expect(
      screen.queryByRole("button", { name: /Generar documento técnico/ }),
    ).not.toBeInTheDocument();
  });

  const CITA =
    'Las bases solicitan un informe técnico: "Se debe entregar informe técnico y certificado individual por cada equipo" (sección 3).';

  it("si las bases lo solicitan, cita la frase y ofrece generarlo con el botón principal", async () => {
    const { onRequestTechnical } = renderViewer(
      listo({ technical_document_ambiguous: true, technical_document_reason: CITA }),
    );

    const bloque = screen.getByRole("region", { name: "Documento técnico" });
    expect(bloque).toHaveTextContent(CITA);
    expect(bloque).toHaveTextContent("Puedes generar un borrador breve a partir de las bases.");
    expect(bloque).not.toHaveTextContent("(opcional)");

    const boton = within(bloque).getByRole("button", { name: /Generar documento técnico/ });
    expect(boton).toHaveClass("bg-primary");
    await userEvent.click(boton);
    expect(onRequestTechnical).toHaveBeenCalled();
  });

  it("no habla de cuándo se entrega ni de si va con la cotización", () => {
    renderViewer(listo({ technical_document_ambiguous: true, technical_document_reason: CITA }));

    const bloque = screen.getByRole("region", { name: "Documento técnico" });
    expect(bloque).not.toHaveTextContent(/cuándo se entrega|va con la cotización|al ejecutar|al finalizar/);
  });

  it("si lo solicitan no ofrece generarlo sin permiso", () => {
    renderViewer(
      listo({ technical_document_ambiguous: true, technical_document_reason: CITA }),
      false,
    );
    expect(
      screen.queryByRole("button", { name: /Generar documento técnico/ }),
    ).not.toBeInTheDocument();
  });

  it("si lo solicitan no ofrece generarlo con la licitación vencida", () => {
    renderViewer(
      listo({
        technical_document_ambiguous: true,
        technical_document_reason: CITA,
        is_expired: true,
      }),
    );
    expect(
      screen.queryByRole("button", { name: /Generar documento técnico/ }),
    ).not.toBeInTheDocument();
  });

  it("un borrador antiguo sin motivo también lo ofrece como opcional", () => {
    renderViewer(listo({ technical_document_ambiguous: null, technical_document_reason: null }));

    const bloque = screen.getByRole("region", { name: "Documento técnico" });
    expect(bloque).toHaveTextContent("Documento técnico (opcional)");
    expect(screen.getByRole("button", { name: /Generar documento técnico/ })).toBeInTheDocument();
  });

  it("bajo cada sección muestra qué poner y la sugerencia para esta licitación", () => {
    renderViewer(
      listo({
        content: {
          ...CONTENIDO,
          technical_document: {
            sections: [
              {
                key: "metodologia",
                title: "Metodología",
                guidance: "Cómo se hará el trabajo, paso a paso.",
                hint: "Indica cómo revisarás los 40 extintores.",
                paragraphs: [{ text: "Clases presenciales.", sources: [], placeholders: [] }],
              },
              {
                key: "equipo",
                title: "Equipo",
                guidance: null,
                hint: null,
                paragraphs: [{ text: "Dos técnicos.", sources: [], placeholders: [] }],
              },
            ],
          },
        },
      }),
    );

    const sugerencias = screen.getAllByTestId("sugerencia-seccion");
    expect(sugerencias).toHaveLength(1);
    expect(sugerencias[0]).toHaveTextContent("Qué poner: Cómo se hará el trabajo, paso a paso.");
    expect(sugerencias[0]).toHaveTextContent(
      "Para esta licitación: Indica cómo revisarás los 40 extintores.",
    );
    // No es un párrafo del borrador: no se puede seleccionar como tal.
    expect(
      screen.queryByRole("button", { name: /Cómo se hará el trabajo/ }),
    ).not.toBeInTheDocument();
  });

  it("una sección con solo sugerencia de la IA muestra solo esa línea", () => {
    renderViewer(
      listo({
        content: {
          ...CONTENIDO,
          technical_document: {
            sections: [
              {
                key: "metodologia",
                title: "Metodología",
                guidance: null,
                hint: "Indica cómo revisarás los 40 extintores.",
                paragraphs: [{ text: "Clases presenciales.", sources: [], placeholders: [] }],
              },
            ],
          },
        },
      }),
    );

    const sugerencia = screen.getByTestId("sugerencia-seccion");
    expect(sugerencia).not.toHaveTextContent("Qué poner");
    expect(sugerencia).toHaveTextContent("Para esta licitación:");
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
