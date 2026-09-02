import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { TenderAssistantDrawer } from "../TenderAssistantDrawer";
import * as useTenderChatModule from "../../hooks/useTenderChat";

// Mock child hooks to isolate drawer rendering
vi.mock("../../hooks/useTenderChat", () => ({
  useTenderChat: vi.fn(),
}));

vi.mock("../../hooks/useTenderDocuments", () => ({
  useTenderDocuments: () => ({
    documents: [
      {
        id: "doc-1",
        tender_id: "tender-1",
        file_name: "terminos_catemu.pdf",
        file_type: "pdf",
        file_size_bytes: 1024 * 500,
        created_at: "2026-06-11T12:00:00Z",
      },
    ],
    isLoading: false,
    isUploading: false,
    error: null,
    uploadDocument: vi.fn(),
    removeDocument: vi.fn(),
  }),
}));

describe("TenderAssistantDrawer", () => {
  it("renderiza el drawer abierto con el título, botón Nuevo Chat y los componentes hijos", () => {
    vi.mocked(useTenderChatModule.useTenderChat).mockReturnValue({
      sessionId: "session-1",
      messages: [
        {
          id: "msg-1",
          session_id: "session-1",
          tender_id: "tender-1",
          user_id: "user-1",
          role: "assistant",
          content: "Hola, soy tu asistente para esta licitación.",
          citations: [],
          created_at: "2026-06-11T12:00:00Z",
        },
      ],
      isLoadingHistory: false,
      isAsking: false,
      isStartingNewChat: false,
      error: null,
      historyError: null,
      loadHistory: vi.fn(),
      startNewChat: vi.fn(),
      retryHistory: vi.fn(),
      sendMessage: vi.fn(),
    });

    render(
      <TenderAssistantDrawer
        tenderId="tender-1"
        tenderTitle="Licitación Catemu"
        isOpen={true}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText(/Asistente Virtual IA/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /nuevo chat/i })).toBeInTheDocument();
    expect(screen.getByText("terminos_catemu.pdf")).toBeInTheDocument();
    expect(
      screen.getByText("Hola, soy tu asistente para esta licitación."),
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/Haz una pregunta sobre esta licitación/i),
    ).toBeInTheDocument();
  });

  it("llama a startNewChat al presionar el botón 'Nuevo Chat'", async () => {
    const startNewChatMock = vi.fn();
    const user = userEvent.setup();

    vi.mocked(useTenderChatModule.useTenderChat).mockReturnValue({
      sessionId: "session-1",
      messages: [],
      isLoadingHistory: false,
      isAsking: false,
      isStartingNewChat: false,
      error: null,
      historyError: null,
      loadHistory: vi.fn(),
      startNewChat: startNewChatMock,
      retryHistory: vi.fn(),
      sendMessage: vi.fn(),
    });

    render(
      <TenderAssistantDrawer
        tenderId="tender-1"
        isOpen={true}
        onClose={vi.fn()}
      />,
    );

    const newChatBtn = screen.getByRole("button", { name: /nuevo chat/i });
    await user.click(newChatBtn);

    expect(startNewChatMock).toHaveBeenCalledOnce();
  });

  it("muestra banner de error y deshabilita el input cuando historyError está presente", () => {
    vi.mocked(useTenderChatModule.useTenderChat).mockReturnValue({
      sessionId: null,
      messages: [],
      isLoadingHistory: false,
      isAsking: false,
      isStartingNewChat: false,
      error: null,
      historyError: "No se pudo cargar el historial de la conversación. Por favor reintente más tarde o inicie un nuevo chat.",
      loadHistory: vi.fn(),
      startNewChat: vi.fn(),
      retryHistory: vi.fn(),
      sendMessage: vi.fn(),
    });

    render(
      <TenderAssistantDrawer
        tenderId="tender-1"
        isOpen={true}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent(/No se pudo cargar el historial de la conversación/i);
    expect(screen.getByText("Reintentar")).toBeInTheDocument();
    const textarea = screen.getByPlaceholderText(/Haz una pregunta sobre esta licitación/i);
    expect(textarea).toBeDisabled();
  });

  it("llama a onClose al hacer clic en el botón de cerrar", async () => {
    const onCloseMock = vi.fn();
    const user = userEvent.setup();

    vi.mocked(useTenderChatModule.useTenderChat).mockReturnValue({
      sessionId: null,
      messages: [],
      isLoadingHistory: false,
      isAsking: false,
      isStartingNewChat: false,
      error: null,
      historyError: null,
      loadHistory: vi.fn(),
      startNewChat: vi.fn(),
      retryHistory: vi.fn(),
      sendMessage: vi.fn(),
    });

    render(
      <TenderAssistantDrawer
        tenderId="tender-1"
        tenderTitle="Licitación Catemu"
        isOpen={true}
        onClose={onCloseMock}
      />,
    );

    const closeBtn = screen.getByRole("button", { name: /cerrar asistente/i });
    await user.click(closeBtn);

    expect(onCloseMock).toHaveBeenCalledOnce();
  });

  it("no se renderiza en el DOM cuando isOpen es false", () => {
    render(
      <TenderAssistantDrawer
        tenderId="tender-1"
        tenderTitle="Licitación Catemu"
        isOpen={false}
        onClose={vi.fn()}
      />,
    );

    expect(screen.queryByText(/Asistente Virtual IA/i)).not.toBeInTheDocument();
  });
});

