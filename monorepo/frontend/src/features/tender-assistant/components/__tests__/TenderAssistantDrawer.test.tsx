import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { TenderAssistantDrawer } from "../TenderAssistantDrawer";

// Mock child hooks to isolate drawer rendering
vi.mock("../../hooks/useTenderChat", () => ({
  useTenderChat: () => ({
    messages: [
      {
        id: "msg-1",
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
    error: null,
    sendMessage: vi.fn(),
  }),
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
  it("renderiza el drawer abierto con el título y los componentes hijos", () => {
    render(
      <TenderAssistantDrawer
        tenderId="tender-1"
        tenderTitle="Licitación Catemu"
        isOpen={true}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText(/Asistente Virtual IA/i)).toBeInTheDocument();
    expect(screen.getByText("terminos_catemu.pdf")).toBeInTheDocument();
    expect(
      screen.getByText("Hola, soy tu asistente para esta licitación."),
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/Haz una pregunta sobre esta licitación/i),
    ).toBeInTheDocument();
  });

  it("llama a onClose al hacer clic en el botón de cerrar", async () => {
    const onCloseMock = vi.fn();
    const user = userEvent.setup();

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
