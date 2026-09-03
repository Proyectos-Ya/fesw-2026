import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { TenderAssistantDrawer } from "../TenderAssistantDrawer";
import * as useTenderChatModule from "../../hooks/useTenderChat";
import * as useTenderDocumentsModule from "../../hooks/useTenderDocuments";

// Mock child hooks to isolate drawer rendering
vi.mock("../../hooks/useTenderChat", () => ({
  useTenderChat: vi.fn(),
}));

vi.mock("../../hooks/useTenderDocuments", () => ({
  useTenderDocuments: vi.fn(),
}));

describe("TenderAssistantDrawer (HU-05.2)", () => {
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

    vi.mocked(useTenderDocumentsModule.useTenderDocuments).mockReturnValue({
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
      canUpload: true,
      maxDocuments: 10,
      clearError: vi.fn(),
      loadDocuments: vi.fn(),
      uploadDocument: vi.fn(),
      removeDocument: vi.fn(),
    });

    render(
      <TenderAssistantDrawer
        tenderId="tender-1"
        tenderTitle="Licitación Catemu"
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByText(/Asistente Virtual IA/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /nuevo chat/i })).toBeInTheDocument();
    expect(screen.getByText("terminos_catemu.pdf")).toBeInTheDocument();
    expect(
      screen.getByText("Hola, soy tu asistente para esta licitación.")
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/Haz una pregunta sobre esta licitación/i)
    ).toBeInTheDocument();
  });

  it("propaga errores de carga/integridad de useTenderDocuments a DocumentAttachmentManager (CA6)", () => {
    vi.mocked(useTenderChatModule.useTenderChat).mockReturnValue({
      sessionId: "session-1",
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

    const docErrorMsg =
      "El archivo 'anexo_danado.pdf' no posee una cabecera PDF válida o está dañado.";

    vi.mocked(useTenderDocumentsModule.useTenderDocuments).mockReturnValue({
      documents: [],
      isLoading: false,
      isUploading: false,
      error: docErrorMsg,
      canUpload: true,
      maxDocuments: 10,
      clearError: vi.fn(),
      loadDocuments: vi.fn(),
      uploadDocument: vi.fn(),
      removeDocument: vi.fn(),
    });

    render(
      <TenderAssistantDrawer
        tenderId="tender-1"
        tenderTitle="Licitación Catemu"
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByText(docErrorMsg)).toBeInTheDocument();
  });

  it("renderiza discrepancias y aspectos sin respaldo dentro del flujo del drawer (CA2 & CA3)", () => {
    vi.mocked(useTenderChatModule.useTenderChat).mockReturnValue({
      sessionId: "session-1",
      messages: [
        {
          id: "msg-multidoc",
          session_id: "session-1",
          tender_id: "tender-1",
          user_id: "user-1",
          role: "assistant",
          content: "Respuesta multidocumento con discrepancia.",
          citations: [
            {
              document_name: "Bases.pdf",
              page_or_sheet: "Pág 2",
              quote: "Plazo de 30 días",
            },
          ],
          discrepancies: [
            {
              topic: "Plazo de entrega",
              description: "Inconsistencia de 30 vs 45 días",
              conflicting_sources: [],
            },
          ],
          unbacked_aspects: ["Monto de garantía"],
          has_sufficient_info: true,
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

    vi.mocked(useTenderDocumentsModule.useTenderDocuments).mockReturnValue({
      documents: [],
      isLoading: false,
      isUploading: false,
      error: null,
      canUpload: true,
      maxDocuments: 10,
      clearError: vi.fn(),
      loadDocuments: vi.fn(),
      uploadDocument: vi.fn(),
      removeDocument: vi.fn(),
    });

    render(
      <TenderAssistantDrawer
        tenderId="tender-1"
        tenderTitle="Licitación Catemu"
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    expect(
      screen.getByText(/Discrepancia detectada: Plazo de entrega/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Aspectos no especificados en los documentos adjuntos:/i)
    ).toBeInTheDocument();
    expect(screen.getByText("Monto de garantía")).toBeInTheDocument();
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

    vi.mocked(useTenderDocumentsModule.useTenderDocuments).mockReturnValue({
      documents: [],
      isLoading: false,
      isUploading: false,
      error: null,
      canUpload: true,
      maxDocuments: 10,
      clearError: vi.fn(),
      loadDocuments: vi.fn(),
      uploadDocument: vi.fn(),
      removeDocument: vi.fn(),
    });

    render(
      <TenderAssistantDrawer
        tenderId="tender-1"
        isOpen={true}
        onClose={vi.fn()}
      />
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
      historyError:
        "No se pudo cargar el historial de la conversación. Por favor reintente más tarde o inicie un nuevo chat.",
      loadHistory: vi.fn(),
      startNewChat: vi.fn(),
      retryHistory: vi.fn(),
      sendMessage: vi.fn(),
    });

    vi.mocked(useTenderDocumentsModule.useTenderDocuments).mockReturnValue({
      documents: [],
      isLoading: false,
      isUploading: false,
      error: null,
      canUpload: true,
      maxDocuments: 10,
      clearError: vi.fn(),
      loadDocuments: vi.fn(),
      uploadDocument: vi.fn(),
      removeDocument: vi.fn(),
    });

    render(
      <TenderAssistantDrawer
        tenderId="tender-1"
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByRole("alert")).toHaveTextContent(
      /No se pudo cargar el historial de la conversación/i
    );
    expect(screen.getByText("Reintentar")).toBeInTheDocument();
    const textarea = screen.getByPlaceholderText(
      /Haz una pregunta sobre esta licitación/i
    );
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

    vi.mocked(useTenderDocumentsModule.useTenderDocuments).mockReturnValue({
      documents: [],
      isLoading: false,
      isUploading: false,
      error: null,
      canUpload: true,
      maxDocuments: 10,
      clearError: vi.fn(),
      loadDocuments: vi.fn(),
      uploadDocument: vi.fn(),
      removeDocument: vi.fn(),
    });

    render(
      <TenderAssistantDrawer
        tenderId="tender-1"
        tenderTitle="Licitación Catemu"
        isOpen={true}
        onClose={onCloseMock}
      />
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
      />
    );

    expect(screen.queryByText(/Asistente Virtual IA/i)).not.toBeInTheDocument();
  });
});
