import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ChatMessageList } from "../ChatMessageList";
import type { TenderChatMessage } from "../../types";

const mockMessages: TenderChatMessage[] = [
  {
    id: "msg-1",
    tender_id: "tender-1",
    user_id: "user-1",
    role: "user",
    content: "¿Dónde se ubica la obra?",
    citations: [],
    created_at: "2026-06-11T12:00:00Z",
  },
  {
    id: "msg-2",
    tender_id: "tender-1",
    user_id: "user-1",
    role: "assistant",
    content: "Se ubica en Catemu, Villa Santa María.",
    citations: [
      {
        document_name: "terminos_referencia.pdf",
        page_or_sheet: "Pág 2",
        quote: "Calle 5 s/n, Villa Santa María, Catemu",
      },
    ],
    created_at: "2026-06-11T12:00:05Z",
  },
];

describe("ChatMessageList (HU-05.2)", () => {
  it("muestra estado vacío cuando no hay mensajes", () => {
    render(<ChatMessageList messages={[]} isAsking={false} />);
    expect(
      screen.getByText(/Haz preguntas sobre las bases, requisitos técnicos/i)
    ).toBeInTheDocument();
  });

  it("renderiza los mensajes del usuario y del asistente con sus citas textuales", () => {
    render(<ChatMessageList messages={mockMessages} isAsking={false} />);

    expect(screen.getByText("¿Dónde se ubica la obra?")).toBeInTheDocument();
    expect(
      screen.getByText("Se ubica en Catemu, Villa Santa María.")
    ).toBeInTheDocument();

    expect(screen.getByText("terminos_referencia.pdf")).toBeInTheDocument();
    expect(screen.getByText("Pág 2")).toBeInTheDocument();
    expect(
      screen.getByText(/"Calle 5 s\/n, Villa Santa María, Catemu"/i)
    ).toBeInTheDocument();
  });

  it("renderiza citas cruzadas desde múltiples documentos (CA1)", () => {
    const multidocMsg: TenderChatMessage = {
      id: "msg-multidoc",
      tender_id: "tender-1",
      user_id: "user-1",
      role: "assistant",
      content: "Respuesta cruzada entre bases y planilla de costos.",
      citations: [
        {
          document_name: "Bases_Administrativas.pdf",
          page_or_sheet: "Pág 3",
          quote: "Requisito de garantía 5%",
        },
        {
          document_name: "Itemizado_Costos.xlsx",
          page_or_sheet: "Hoja 1",
          quote: "Costo unitario $50.000",
        },
      ],
      created_at: "2026-06-11T12:00:10Z",
    };

    render(<ChatMessageList messages={[multidocMsg]} isAsking={false} />);

    expect(screen.getByText("Bases_Administrativas.pdf")).toBeInTheDocument();
    expect(screen.getByText("Pág 3")).toBeInTheDocument();
    expect(screen.getByText("Itemizado_Costos.xlsx")).toBeInTheDocument();
    expect(screen.getByText("Hoja 1")).toBeInTheDocument();
  });

  it("renderiza DiscrepancyCard cuando el mensaje contiene discrepancias detectadas (CA2)", () => {
    const discrepancyMsg: TenderChatMessage = {
      id: "msg-disc",
      tender_id: "tender-1",
      user_id: "user-1",
      role: "assistant",
      content: "Se detectó una discrepancia en el plazo.",
      citations: [],
      discrepancies: [
        {
          topic: "Plazo de ejecución",
          description: "Bases dicen 30 días y especificaciones 45 días.",
          conflicting_sources: [
            {
              document_name: "Bases.pdf",
              page_or_sheet: "Pág 4",
              quote: "Plazo de 30 días",
            },
          ],
        },
      ],
      created_at: "2026-06-11T12:00:15Z",
    };

    render(<ChatMessageList messages={[discrepancyMsg]} isAsking={false} />);

    expect(
      screen.getByText(/Discrepancia detectada: Plazo de ejecución/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Bases dicen 30 días y especificaciones 45 días./i)
    ).toBeInTheDocument();
  });

  it("renderiza UnbackedAspectsList e InsufficientInfoBanner cuando hay respaldo parcial o información inexistente (CA3 & CA4)", () => {
    const partialMsg: TenderChatMessage = {
      id: "msg-partial",
      tender_id: "tender-1",
      user_id: "user-1",
      role: "assistant",
      content: "Respuesta con aspectos no detallados.",
      citations: [],
      unbacked_aspects: ["Requisito de certificación ISO 9001"],
      has_sufficient_info: false,
      created_at: "2026-06-11T12:00:20Z",
    };

    render(<ChatMessageList messages={[partialMsg]} isAsking={false} />);

    expect(
      screen.getByText(/Aspectos no especificados en los documentos adjuntos:/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText("Requisito de certificación ISO 9001")
    ).toBeInTheDocument();

    expect(
      screen.getByText(/Información no especificada en las bases/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /Se sugiere realizar la consulta formal mediante el Foro de Preguntas/i
      )
    ).toBeInTheDocument();
  });

  it("renderiza advertencias cuando el mensaje contiene warnings de archivos dañados (CA6)", () => {
    const warningMsg: TenderChatMessage = {
      id: "msg-warn",
      tender_id: "tender-1",
      user_id: "user-1",
      role: "assistant",
      content: "Respuesta con los documentos sanos restantes.",
      citations: [],
      warnings: [
        "El documento 'anexo_corrupto.pdf' está dañado y no pudo ser procesado.",
      ],
      created_at: "2026-06-11T12:00:25Z",
    };

    render(<ChatMessageList messages={[warningMsg]} isAsking={false} />);

    expect(
      screen.getByText(
        /El documento 'anexo_corrupto.pdf' está dañado y no pudo ser procesado./i
      )
    ).toBeInTheDocument();
  });

  it("muestra indicador de carga cuando isAsking es true", () => {
    render(<ChatMessageList messages={mockMessages} isAsking={true} />);
    expect(screen.getByText(/Analizando documentos/i)).toBeInTheDocument();
  });

  it("muestra alerta de error si el asistente está fuera de servicio", () => {
    render(
      <ChatMessageList
        messages={[]}
        isAsking={false}
        error="El asistente virtual se encuentra temporalmente fuera de servicio"
      />
    );

    expect(
      screen.getByText(
        /El asistente virtual se encuentra temporalmente fuera de servicio/i
      )
    ).toBeInTheDocument();
  });
});
