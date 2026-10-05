import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DocumentAttachmentManager } from "../DocumentAttachmentManager";
import type { TenderChatDocument } from "../../types";

const mockDocs: TenderChatDocument[] = [
  {
    id: "doc-1",
    tender_id: "tender-1",
    file_name: "especificaciones.pdf",
    file_type: "pdf",
    file_size_bytes: 1024 * 500, // 500 KB
    created_at: "2026-06-11T12:00:00Z",
  },
  {
    id: "doc-2",
    tender_id: "tender-1",
    file_name: "itemizado.xlsx",
    file_type: "xlsx",
    file_size_bytes: 1024 * 100, // 100 KB
    created_at: "2026-06-11T12:00:00Z",
  },
];

describe("DocumentAttachmentManager (Decisión 5 / Plan 233)", () => {
  it("muestra el banner informativo de bases oficiales y no incluye input de archivo", () => {
    render(
      <DocumentAttachmentManager
        documents={[]}
        onDelete={vi.fn()}
        onNavigateToPanel={vi.fn()}
      />
    );

    expect(screen.getByText("Bases y anexos oficiales sincronizados")).toBeInTheDocument();
    expect(screen.queryByTestId("file-upload-input")).toBeNull();
    expect(screen.queryByRole("button", { name: /adjuntar/i })).toBeNull();
  });

  it("invoca onNavigateToPanel al hacer clic en 'Ver panel'", async () => {
    const onNavigateToPanel = vi.fn();
    const user = userEvent.setup();

    render(
      <DocumentAttachmentManager
        documents={[]}
        onDelete={vi.fn()}
        onNavigateToPanel={onNavigateToPanel}
      />
    );

    const verPanelBtn = screen.getByRole("button", { name: "Ver panel" });
    await user.click(verPanelBtn);

    expect(onNavigateToPanel).toHaveBeenCalledOnce();
  });

  it("renderiza documentos legacy del chat con badge 'Chat antiguo'", () => {
    render(
      <DocumentAttachmentManager
        documents={mockDocs}
        onDelete={vi.fn()}
      />
    );

    expect(screen.getByText("Archivos del chat (2)")).toBeInTheDocument();
    expect(screen.getByText("especificaciones.pdf")).toBeInTheDocument();
    expect(screen.getByText("itemizado.xlsx")).toBeInTheDocument();
    expect(screen.getByText("500.0 KB")).toBeInTheDocument();

    const badges = screen.getAllByText("Chat antiguo");
    expect(badges).toHaveLength(2);
  });

  it("permite eliminar documentos legacy con onDelete", async () => {
    const onDeleteMock = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();

    render(
      <DocumentAttachmentManager
        documents={mockDocs}
        onDelete={onDeleteMock}
      />
    );

    const deleteBtns = screen.getAllByRole("button", {
      name: /eliminar documento/i,
    });
    await user.click(deleteBtns[0]);

    expect(onDeleteMock).toHaveBeenCalledWith("doc-1");
  });

  it("renderiza mensaje de error externo si existe", () => {
    const errorMsg = "Error al procesar archivo anterior";

    render(
      <DocumentAttachmentManager
        documents={mockDocs}
        onDelete={vi.fn()}
        externalError={errorMsg}
      />
    );

    expect(screen.getByText(errorMsg)).toBeInTheDocument();
  });
});
