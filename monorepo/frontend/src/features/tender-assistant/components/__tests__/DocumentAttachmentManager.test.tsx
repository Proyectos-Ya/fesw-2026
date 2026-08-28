import { render, screen, fireEvent } from "@testing-library/react";
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

describe("DocumentAttachmentManager", () => {
  it("renderiza la lista de documentos adjuntos", () => {
    render(
      <DocumentAttachmentManager
        documents={mockDocs}
        onUpload={vi.fn()}
        onDelete={vi.fn()}
        isUploading={false}
      />,
    );

    expect(screen.getByText("especificaciones.pdf")).toBeInTheDocument();
    expect(screen.getByText("itemizado.xlsx")).toBeInTheDocument();
    expect(screen.getByText("500.0 KB")).toBeInTheDocument();
  });

  it("permite subir un archivo PDF válido", async () => {
    const onUploadMock = vi.fn().mockResolvedValue(undefined);
    render(
      <DocumentAttachmentManager
        documents={[]}
        onUpload={onUploadMock}
        onDelete={vi.fn()}
        isUploading={false}
      />,
    );

    const input = screen.getByTestId("file-upload-input");
    const file = new File(["dummy pdf"], "bases.pdf", { type: "application/pdf" });

    fireEvent.change(input, { target: { files: [file] } });

    expect(onUploadMock).toHaveBeenCalledWith(file);
  });

  it("rechaza archivos con extensiones no permitidas (.exe, .zip)", () => {
    const onUploadMock = vi.fn();
    render(
      <DocumentAttachmentManager
        documents={[]}
        onUpload={onUploadMock}
        onDelete={vi.fn()}
        isUploading={false}
      />,
    );

    const input = screen.getByTestId("file-upload-input");
    const file = new File(["dummy exe"], "script.exe", { type: "application/x-msdownload" });

    fireEvent.change(input, { target: { files: [file] } });

    expect(onUploadMock).not.toHaveBeenCalled();
    expect(
      screen.getByText(/Solo se permiten archivos PDF, Excel/i),
    ).toBeInTheDocument();
  });

  it("llama a onDelete al hacer clic en el botón de eliminar", async () => {
    const onDeleteMock = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();

    render(
      <DocumentAttachmentManager
        documents={mockDocs}
        onUpload={vi.fn()}
        onDelete={onDeleteMock}
        isUploading={false}
      />,
    );

    const deleteBtns = screen.getAllByRole("button", { name: /eliminar documento/i });
    await user.click(deleteBtns[0]);

    expect(onDeleteMock).toHaveBeenCalledWith("doc-1");
  });
});
