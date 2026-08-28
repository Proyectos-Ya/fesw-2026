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

describe("ChatMessageList", () => {
  it("muestra estado vacío cuando no hay mensajes", () => {
    render(<ChatMessageList messages={[]} isAsking={false} />);
    expect(
      screen.getByText(/Haz preguntas sobre las bases, requisitos técnicos/i),
    ).toBeInTheDocument();
  });

  it("renderiza los mensajes del usuario y del asistente con sus citas textuales", () => {
    render(<ChatMessageList messages={mockMessages} isAsking={false} />);

    expect(screen.getByText("¿Dónde se ubica la obra?")).toBeInTheDocument();
    expect(
      screen.getByText("Se ubica en Catemu, Villa Santa María."),
    ).toBeInTheDocument();

    expect(screen.getByText("terminos_referencia.pdf")).toBeInTheDocument();
    expect(screen.getByText("Pág 2")).toBeInTheDocument();
    expect(
      screen.getByText(/"Calle 5 s\/n, Villa Santa María, Catemu"/i),
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
      />,
    );

    expect(
      screen.getByText(/El asistente virtual se encuentra temporalmente fuera de servicio/i),
    ).toBeInTheDocument();
  });
});
