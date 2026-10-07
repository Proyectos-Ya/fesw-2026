import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/features/shared/api/client";
import { formatDateTime } from "@/features/matches/utils/format";
import * as storage from "../../services/storageUpload";
import * as service from "../../services/tenderAttachmentsService";
import {
  buildAttachmentFile,
  buildOfficialAttachment,
  buildTenderAttachments,
  buildUploadTicket,
} from "../../test-utils";
import { SHARING_NOTICES } from "../../utils/sharing";
import { clearTenderAttachmentsCache } from "../../hooks/useTenderAttachments";
import { TenderAttachmentsPanel } from "../TenderAttachmentsPanel";

vi.mock("../../services/tenderAttachmentsService", () => ({
  getTenderAttachments: vi.fn(),
  requestUploadUrl: vi.fn(),
  completeUpload: vi.fn(),
  deleteAttachmentFile: vi.fn(),
}));

// Se conserva `StorageUploadError` real: el hook decide el mensaje según su clase.
vi.mock("../../services/storageUpload", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../services/storageUpload")>()),
  putToStorage: vi.fn(),
}));

const FICHA = "https://buscador.mercadopublico.cl/ficha?code=5052-431-COT26";
const NOMBRE_OFICIAL = "Anexo 3 Composición personalidad juridica.xlsx";
const SHA_HOLA = "b221d9dbb083a7f33428d7c2a3c3198ae925614d70210e28716ccaa7cd4ddb79";

function renderPanel() {
  return render(<TenderAttachmentsPanel tenderId="t-1" tenderCode="5052-431-COT26" />);
}

function fichaLink() {
  return screen.getByRole("link", { name: /ver documentos en mercado público/i });
}

function archivoDescargado() {
  return new File(["hola"], "anexo 3 composicion personalidad juridica (1).XLSX");
}

describe("TenderAttachmentsPanel", () => {
  beforeEach(() => {
    clearTenderAttachmentsCache();
    window.localStorage.clear();
    vi.mocked(service.getTenderAttachments).mockReset();
  });

  it("mientras carga avisa y deja a mano la ficha oficial", () => {
    vi.mocked(service.getTenderAttachments).mockReturnValue(new Promise(() => {}));

    renderPanel();

    expect(screen.getByRole("status")).toHaveTextContent("Cargando anexos de la licitación…");
    expect(fichaLink()).toHaveAttribute("href", FICHA);
    expect(fichaLink()).toHaveAttribute("target", "_blank");
  });

  it("lista cada documento subido con su extensión y su estado", async () => {
    vi.mocked(service.getTenderAttachments).mockResolvedValue(
      buildTenderAttachments({
        official: [
          buildOfficialAttachment({
            status: "stored",
            file: buildAttachmentFile(),
          }),
          buildOfficialAttachment({
            id: "a-2",
            mp_document_id: 1931003,
            name: "anexos (1,1-A, 2).docx",
            ext: "docx",
            status: "stored",
            file: buildAttachmentFile({ id: "f-2" }),
          }),
        ],
      }),
    );

    renderPanel();

    const items = await screen.findAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(within(items[0]).getByText("Anexo 3 Composición personalidad juridica.xlsx")).toBeVisible();
    expect(within(items[0]).getByText("XLSX")).toBeVisible();
    expect(within(items[0]).getByText("Subido")).toBeVisible();
    expect(within(items[1]).getByText("anexos (1,1-A, 2).docx")).toBeVisible();
    expect(within(items[1]).getByText("DOCX")).toBeVisible();
    expect(within(items[1]).getByText("Subido")).toBeVisible();
    expect(service.getTenderAttachments).toHaveBeenCalledWith("t-1");
  });

  it("no muestra la insignia de extensión cuando el nombre no la trae", async () => {
    vi.mocked(service.getTenderAttachments).mockResolvedValue(
      buildTenderAttachments({
        official: [
          buildOfficialAttachment({
            name: "Bases",
            ext: "",
            status: "stored",
            file: buildAttachmentFile(),
          }),
        ],
      }),
    );

    renderPanel();

    const [item] = await screen.findAllByRole("listitem");
    expect(within(item).getByText("Bases")).toBeVisible();
    expect(within(item).getByText("Subido")).toBeVisible();
    expect(within(item).queryByText("XLSX")).not.toBeInTheDocument();
  });

  it("sin archivos subidos no renderiza la lista y deja disponible la zona de subida", async () => {
    vi.mocked(service.getTenderAttachments).mockResolvedValue(
      buildTenderAttachments({ official: [], can_upload: true }),
    );

    renderPanel();

    expect(screen.queryByRole("list")).not.toBeInTheDocument();
    expect(await screen.findByTestId("attachments-drop-zone")).toBeVisible();
    expect(fichaLink()).toHaveAttribute("href", FICHA);
  });

  it("ante un error muestra el mensaje, conserva el enlace y permite reintentar", async () => {
    const user = userEvent.setup();
    vi.mocked(service.getTenderAttachments)
      .mockRejectedValueOnce(new ApiError(500, "Falló el servidor"))
      .mockResolvedValueOnce(
        buildTenderAttachments({
          official: [buildOfficialAttachment({ file: buildAttachmentFile() })],
        }),
      );

    renderPanel();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Falló el servidor");
    expect(fichaLink()).toBeVisible();

    await user.click(within(alert).getByRole("button", { name: "Reintentar" }));

    expect(await screen.findAllByRole("listitem")).toHaveLength(1);
    expect(service.getTenderAttachments).toHaveBeenCalledTimes(2);
  });
});

describe("TenderAttachmentsPanel — subida manual (plan 233, decisión 2)", () => {
  beforeEach(() => {
    clearTenderAttachmentsCache();
    window.localStorage.clear();
    vi.mocked(service.getTenderAttachments)
      .mockReset()
      .mockResolvedValue(
        buildTenderAttachments({
          can_upload: true,
          official: [buildOfficialAttachment({ file: buildAttachmentFile() })],
        }),
      );
    vi.mocked(service.requestUploadUrl).mockReset().mockResolvedValue(buildUploadTicket());
    vi.mocked(service.completeUpload).mockReset().mockResolvedValue(buildAttachmentFile());
    vi.mocked(service.deleteAttachmentFile).mockReset().mockResolvedValue(undefined);
    vi.mocked(storage.putToStorage).mockReset().mockResolvedValue(undefined);
  });

  function filas() {
    return within(screen.getByRole("list", { name: "Documentos subidos" }));
  }

  it("muestra la zona para arrastrar solo si la empresa puede subir", async () => {
    renderPanel();
    expect(await screen.findByTestId("attachments-drop-zone")).toBeVisible();
    expect(screen.getByLabelText("Elegir anexos para subir")).toBeInTheDocument();
  });

  it("sin permiso para subir no hay zona, ni botón Subir, ni Borrar", async () => {
    vi.mocked(service.getTenderAttachments).mockResolvedValue(
      buildTenderAttachments({
        can_upload: false,
        official: [
          buildOfficialAttachment({
            status: "stored",
            file: buildAttachmentFile(),
          }),
        ],
      }),
    );

    renderPanel();

    await screen.findByText("Subido");
    expect(screen.queryByTestId("attachments-drop-zone")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Subir" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Borrar/ })).not.toBeInTheDocument();
    expect(fichaLink()).toBeVisible();
  });

  it("al soltar un archivo lo asigna a su anexo y lo sube", async () => {
    vi.mocked(service.getTenderAttachments).mockResolvedValue(
      buildTenderAttachments({
        can_upload: true,
        official: [buildOfficialAttachment({ file: null })],
      }),
    );
    const file = archivoDescargado();
    renderPanel();
    const zona = await screen.findByTestId("attachments-drop-zone");

    fireEvent.drop(zona, { dataTransfer: { files: [file] } });

    await waitFor(() => expect(service.completeUpload).toHaveBeenCalledWith("t-1", "u-1"));
    expect(service.requestUploadUrl).toHaveBeenCalledWith("t-1", "a-1", {
      file_name: file.name,
      size_bytes: 4,
      mime: "",
      sha256: SHA_HOLA,
    });
    expect(storage.putToStorage).toHaveBeenCalledWith(
      expect.objectContaining({
        url: "https://almacen.test/put",
        headers: buildUploadTicket().headers,
        body: file,
      }),
    );
    await waitFor(() => expect(service.getTenderAttachments).toHaveBeenCalledTimes(2));
  });

  it("acepta un archivo con nombre distinto al soltarlo y lo sube sin exigir nombre oficial", async () => {
    vi.mocked(service.getTenderAttachments).mockResolvedValue(
      buildTenderAttachments({
        can_upload: true,
        official: [buildOfficialAttachment({ file: null })],
      }),
    );
    renderPanel();
    const zona = await screen.findByTestId("attachments-drop-zone");

    fireEvent.drop(zona, {
      dataTransfer: { files: [new File(["x"], "COTIZACION OFICINA LOGISTICA DEAOPERPOL.xlsx")] },
    });

    await waitFor(() => expect(service.completeUpload).toHaveBeenCalledWith("t-1", "u-1"));
    expect(service.requestUploadUrl).toHaveBeenCalledWith("t-1", "a-1", expect.anything());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("bloquea la ui con un loader mientras se procesan y suben los archivos", async () => {
    let resolveStorage: (() => void) | undefined;
    vi.mocked(service.getTenderAttachments).mockResolvedValue(
      buildTenderAttachments({
        can_upload: true,
        official: [buildOfficialAttachment({ file: null })],
      }),
    );
    vi.mocked(storage.putToStorage).mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolveStorage = resolve;
        }),
    );

    renderPanel();
    const zona = await screen.findByTestId("attachments-drop-zone");

    fireEvent.drop(zona, {
      dataTransfer: { files: [archivoDescargado()] },
    });

    // Mientras sube: el loader bloquea la UI y la zona de arrastre se deshabilita
    expect(await screen.findByTestId("attachments-processing-loader")).toBeVisible();
    expect(screen.getByText("Procesando archivos…")).toBeVisible();
    expect(zona).toHaveClass("pointer-events-none");

    // Al terminar de subir: el loader desaparece
    await waitFor(() => expect(resolveStorage).toBeDefined());
    resolveStorage?.();
    await waitFor(() => {
      expect(screen.queryByTestId("attachments-processing-loader")).not.toBeInTheDocument();
    });
  });

  it("permite elegir un archivo desde el selector de la zona de subida", async () => {
    vi.mocked(service.getTenderAttachments).mockResolvedValue(
      buildTenderAttachments({
        can_upload: true,
        official: [buildOfficialAttachment({ file: null })],
      }),
    );
    renderPanel();
    const input = await screen.findByLabelText("Elegir anexos para subir");

    fireEvent.change(input, {
      target: { files: [archivoDescargado()] },
    });

    await waitFor(() => expect(service.completeUpload).toHaveBeenCalledWith("t-1", "u-1"));
    expect(service.requestUploadUrl).toHaveBeenCalledWith("t-1", "a-1", expect.anything());
  });

  it("acepta un archivo con nombre distinto sin validar el nombre oficial", async () => {
    vi.mocked(service.getTenderAttachments).mockResolvedValue(
      buildTenderAttachments({
        can_upload: true,
        official: [buildOfficialAttachment({ file: null })],
      }),
    );
    renderPanel();
    const input = await screen.findByLabelText("Elegir anexos para subir");

    fireEvent.change(input, {
      target: { files: [new File(["hola"], "documento_descargado_1058043.xlsx")] },
    });

    await waitFor(() => expect(service.requestUploadUrl).toHaveBeenCalledWith("t-1", "a-1", expect.anything()));
  });

  it("muestra el archivo subido y deja borrarlo si es propio", async () => {
    const user = userEvent.setup();
    vi.mocked(service.getTenderAttachments).mockResolvedValue(
      buildTenderAttachments({
        can_upload: true,
        official: [
          buildOfficialAttachment({
            status: "stored",
            file: buildAttachmentFile({ id: "f-1", size_bytes: 2048 }),
          }),
        ],
      }),
    );
    renderPanel();

    const [fila] = await screen.findAllByRole("listitem");
    expect(within(fila).getByText("Subido")).toBeVisible();
    expect(within(fila).getByText("2.0 KB")).toBeVisible();
    expect(within(fila).getByText("Solo tu empresa")).toBeVisible();
    expect(within(fila).queryByRole("button", { name: "Subir" })).not.toBeInTheDocument();

    await user.click(
      within(fila).getByRole("button", { name: `Borrar el archivo de ${NOMBRE_OFICIAL}` }),
    );

    await waitFor(() =>
      expect(service.deleteAttachmentFile).toHaveBeenCalledWith("t-1", "f-1"),
    );
    await waitFor(() => expect(service.getTenderAttachments).toHaveBeenCalledTimes(2));
  });

  it("no ofrece Borrar un archivo compartido de otra empresa", async () => {
    vi.mocked(service.getTenderAttachments).mockResolvedValue(
      buildTenderAttachments({
        can_upload: true,
        official: [
          buildOfficialAttachment({
            status: "stored",
            file: buildAttachmentFile({ visibility: "shared", is_mine: false }),
          }),
        ],
      }),
    );

    renderPanel();

    expect(await screen.findByText("Compartido")).toBeVisible();
    expect(screen.queryByRole("button", { name: /Borrar/ })).not.toBeInTheDocument();
  });

  it('muestra "Solo tu empresa" en un archivo propio sin confirmar', async () => {
    vi.mocked(service.getTenderAttachments).mockResolvedValue(
      buildTenderAttachments({
        official: [
          buildOfficialAttachment({
            status: "stored",
            file: buildAttachmentFile(),
          }),
        ],
      }),
    );
    renderPanel();

    await screen.findByText(NOMBRE_OFICIAL);
    expect(filas().getByText("Solo tu empresa")).toBeVisible();
    expect(filas().queryByRole("note")).toBeNull();
  });

  it('muestra "Compartido" y no ofrece Borrar en un archivo propio ya confirmado', async () => {
    vi.mocked(service.getTenderAttachments).mockResolvedValue(
      buildTenderAttachments({
        can_upload: true,
        official: [
          buildOfficialAttachment({
            status: "stored",
            file: buildAttachmentFile({ visibility: "shared", trust: "corroborated" }),
          }),
        ],
      }),
    );
    renderPanel();

    await screen.findByText(NOMBRE_OFICIAL);
    expect(filas().getByText("Compartido")).toBeVisible();
    expect(filas().queryByRole("button", { name: /borrar el archivo/i })).toBeNull();
  });

  it('muestra "Compartido" en el archivo que confirmaron otras fuentes', async () => {
    vi.mocked(service.getTenderAttachments).mockResolvedValue(
      buildTenderAttachments({
        official: [
          buildOfficialAttachment({
            status: "stored",
            file: buildAttachmentFile({ is_mine: false, visibility: "shared" }),
          }),
        ],
      }),
    );
    renderPanel();

    await screen.findByText(NOMBRE_OFICIAL);
    expect(filas().getByText("Compartido")).toBeVisible();
    expect(filas().queryByRole("note")).toBeNull();
  });

  it("avisa el conflicto en un archivo propio y deja borrarlo", async () => {
    vi.mocked(service.getTenderAttachments).mockResolvedValue(
      buildTenderAttachments({
        can_upload: true,
        official: [
          buildOfficialAttachment({
            status: "stored",
            file: buildAttachmentFile({ is_mine: true, visibility: "private", trust: "conflict" }),
          }),
        ],
      }),
    );
    renderPanel();

    await screen.findByText(NOMBRE_OFICIAL);
    expect(filas().getByRole("note")).toHaveTextContent(SHARING_NOTICES.conflict);
    expect(filas().getByRole("button", { name: /borrar el archivo/i })).toBeVisible();
  });

  it("avisa que el archivo propio no coincide con la versión confirmada", async () => {
    vi.mocked(service.getTenderAttachments).mockResolvedValue(
      buildTenderAttachments({
        official: [
          buildOfficialAttachment({
            status: "stored",
            file: buildAttachmentFile({ is_mine: true, visibility: "private", trust: "rejected" }),
          }),
        ],
      }),
    );
    renderPanel();

    await screen.findByText(NOMBRE_OFICIAL);
    expect(filas().getByRole("note")).toHaveTextContent(SHARING_NOTICES.rejected);
  });

  it("no muestra avisos en un anexo sin archivo", async () => {
    vi.mocked(service.getTenderAttachments).mockResolvedValue(
      buildTenderAttachments({
        official: [
          buildOfficialAttachment({
            status: "missing",
            file: null,
          }),
        ],
      }),
    );
    renderPanel();

    expect(screen.queryByRole("list")).toBeNull();
    expect(screen.queryByRole("note")).toBeNull();
  });

  it("muestra el cupo y avisa cuando se alcanzó el tope", async () => {
    vi.mocked(service.getTenderAttachments).mockResolvedValue(
      buildTenderAttachments({ can_upload: true, quota: { used: 3, limit: 100 } }),
    );
    const { unmount } = renderPanel();

    expect(
      await screen.findByText("Subidas de anexos de tu empresa este mes: 3 de 100."),
    ).toBeVisible();
    expect(screen.queryByText(/Alcanzaste el tope/)).not.toBeInTheDocument();
    unmount();

    vi.mocked(service.getTenderAttachments).mockResolvedValue(
      buildTenderAttachments({ can_upload: true, quota: { used: 100, limit: 100 } }),
    );
    renderPanel();

    expect(
      await screen.findByText("Subidas de anexos de tu empresa este mes: 100 de 100."),
    ).toBeVisible();
    expect(screen.getByText("Alcanzaste el tope de subidas de este mes.")).toBeVisible();
  });

  it("el error de cupo se muestra en la fila y se puede reintentar", async () => {
    const user = userEvent.setup();
    const detalle = "Tu empresa alcanzó el tope de 100 subidas de anexos de este mes.";
    vi.mocked(service.getTenderAttachments).mockResolvedValue(
      buildTenderAttachments({
        can_upload: true,
        official: [buildOfficialAttachment({ file: null })],
      }),
    );
    vi.mocked(service.requestUploadUrl).mockRejectedValueOnce(
      new ApiError(403, detalle, "quota_exceeded", { used: 100, limit: 100 }),
    );
    renderPanel();

    const input = await screen.findByLabelText("Elegir anexos para subir");
    fireEvent.change(input, {
      target: { files: [archivoDescargado()] },
    });

    expect(await screen.findByText(detalle)).toBeVisible();
    await user.click(filas().getByRole("button", { name: "Reintentar" }));

    await waitFor(() => expect(service.completeUpload).toHaveBeenCalledWith("t-1", "u-1"));
    expect(service.requestUploadUrl).toHaveBeenCalledTimes(2);
  });

  it("muestra el progreso de la subida", async () => {
    vi.mocked(service.getTenderAttachments).mockResolvedValue(
      buildTenderAttachments({
        can_upload: true,
        official: [buildOfficialAttachment({ file: null })],
      }),
    );
    vi.mocked(storage.putToStorage).mockImplementation(({ onProgress }) => {
      onProgress?.(0.5);
      return new Promise(() => {});
    });
    renderPanel();

    const input = await screen.findByLabelText("Elegir anexos para subir");
    fireEvent.change(input, {
      target: { files: [archivoDescargado()] },
    });

    const barra = await screen.findByRole("progressbar");
    expect(barra).toHaveAttribute("aria-valuenow", "50");
    expect(screen.getByText("Subiendo 50 %")).toBeVisible();
  });

  describe("integración con Digest", () => {
    it("con una fila ready: notifica onReadyKeyChange con el id del archivo", async () => {
      const onReadyKeyChange = vi.fn();
      vi.mocked(service.getTenderAttachments).mockResolvedValue(
        buildTenderAttachments({
          official: [
            buildOfficialAttachment({
              id: "a-1",
              status: "stored",
              processing: "ready",
              file: buildAttachmentFile({ id: "f-1" }),
            }),
          ],
        })
      );

      const { unmount } = render(
        <TenderAttachmentsPanel
          tenderId="t-1"
          tenderCode="5052-431-COT26"
          onReadyKeyChange={onReadyKeyChange}
        />
      );

      await waitFor(() => {
        expect(onReadyKeyChange).toHaveBeenCalledWith("f-1");
      });
      unmount();
    });

    it("sin filas ready: onReadyKeyChange se llama con string vacío", async () => {
      const onReadyKeyChange = vi.fn();
      vi.mocked(service.getTenderAttachments).mockResolvedValue(
        buildTenderAttachments({
          can_upload: true,
          official: [
            buildOfficialAttachment({
              id: "a-1",
              status: "missing",
              processing: null,
            }),
          ],
        })
      );

      render(
        <TenderAttachmentsPanel
          tenderId="t-1"
          tenderCode="5052-431-COT26"
          onReadyKeyChange={onReadyKeyChange}
        />
      );
      await screen.findByTestId("attachments-drop-zone");

      expect(onReadyKeyChange).toHaveBeenCalledWith("");
    });

    it("con processing_enabled: false y una fila processing muestra aviso de desactivado", async () => {
      vi.mocked(service.getTenderAttachments).mockResolvedValue(
        buildTenderAttachments({
          processing_enabled: false,
          official: [
            buildOfficialAttachment({
              id: "a-1",
              status: "stored",
              processing: "processing",
              file: buildAttachmentFile({ id: "f-1" }),
            }),
          ],
        })
      );

      renderPanel();

      expect(
        await screen.findByText("El resumen automático de anexos está desactivado en este entorno.")
      ).toBeInTheDocument();
    });
  });
});

