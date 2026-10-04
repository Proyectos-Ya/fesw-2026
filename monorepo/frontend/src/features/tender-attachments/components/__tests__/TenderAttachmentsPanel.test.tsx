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
    vi.mocked(service.getTenderAttachments).mockReset();
  });

  it("mientras carga avisa y deja a mano la ficha oficial", () => {
    vi.mocked(service.getTenderAttachments).mockReturnValue(new Promise(() => {}));

    renderPanel();

    expect(screen.getByRole("status")).toHaveTextContent("Cargando anexos de la licitación…");
    expect(fichaLink()).toHaveAttribute("href", FICHA);
    expect(fichaLink()).toHaveAttribute("target", "_blank");
  });

  it("lista cada anexo con su extensión y su estado", async () => {
    vi.mocked(service.getTenderAttachments).mockResolvedValue(
      buildTenderAttachments({
        official: [
          buildOfficialAttachment(),
          buildOfficialAttachment({
            id: "a-2",
            mp_document_id: 1931003,
            name: "anexos (1,1-A, 2).docx",
            ext: "docx",
          }),
        ],
      }),
    );

    renderPanel();

    const items = await screen.findAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(within(items[0]).getByText("Anexo 3 Composición personalidad juridica.xlsx")).toBeVisible();
    expect(within(items[0]).getByText("XLSX")).toBeVisible();
    expect(within(items[0]).getByText("Falta")).toBeVisible();
    expect(within(items[1]).getByText("anexos (1,1-A, 2).docx")).toBeVisible();
    expect(within(items[1]).getByText("DOCX")).toBeVisible();
    expect(service.getTenderAttachments).toHaveBeenCalledWith("t-1");
    expect(
      screen.getByText(
        `Lista sincronizada con Mercado Público el ${formatDateTime("2026-09-28T16:28:00Z")}.`,
      ),
    ).toBeVisible();
  });

  it("no muestra la insignia de extensión cuando el nombre no la trae", async () => {
    vi.mocked(service.getTenderAttachments).mockResolvedValue(
      buildTenderAttachments({
        official: [buildOfficialAttachment({ name: "Bases", ext: "" })],
      }),
    );

    renderPanel();

    const [item] = await screen.findAllByRole("listitem");
    expect(within(item).getByText("Bases")).toBeVisible();
    expect(within(item).getByText("Falta")).toBeVisible();
    expect(within(item).queryByText("XLSX")).not.toBeInTheDocument();
  });

  it("sin lista y sin sincronizar dice que todavía no la tiene", async () => {
    vi.mocked(service.getTenderAttachments).mockResolvedValue(
      buildTenderAttachments({ official: [], list_synced_at: null }),
    );

    renderPanel();

    expect(await screen.findByText(/Todavía no tenemos la lista de anexos/)).toBeVisible();
    expect(fichaLink()).toHaveAttribute("href", FICHA);
  });

  it("sin anexos y sincronizada dice que Mercado Público no informa ninguno", async () => {
    vi.mocked(service.getTenderAttachments).mockResolvedValue(
      buildTenderAttachments({ official: [] }),
    );

    renderPanel();

    expect(
      await screen.findByText("Mercado Público no informa anexos para esta licitación."),
    ).toBeVisible();
    expect(screen.queryByText(/Todavía no tenemos/)).not.toBeInTheDocument();
  });

  it("ante un error muestra el mensaje, conserva el enlace y permite reintentar", async () => {
    const user = userEvent.setup();
    vi.mocked(service.getTenderAttachments)
      .mockRejectedValueOnce(new ApiError(500, "Falló el servidor"))
      .mockResolvedValueOnce(buildTenderAttachments());

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
    vi.mocked(service.getTenderAttachments)
      .mockReset()
      .mockResolvedValue(buildTenderAttachments({ can_upload: true }));
    vi.mocked(service.requestUploadUrl).mockReset().mockResolvedValue(buildUploadTicket());
    vi.mocked(service.completeUpload).mockReset().mockResolvedValue(buildAttachmentFile());
    vi.mocked(service.deleteAttachmentFile).mockReset().mockResolvedValue(undefined);
    vi.mocked(storage.putToStorage).mockReset().mockResolvedValue(undefined);
  });

  function filas() {
    return within(screen.getByRole("list", { name: "Anexos oficiales" }));
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

  it("rechaza un archivo que no calza y lista los nombres esperados", async () => {
    renderPanel();
    const zona = await screen.findByTestId("attachments-drop-zone");

    fireEvent.drop(zona, { dataTransfer: { files: [new File(["x"], "otro.pdf")] } });

    const alerta = await screen.findByRole("alert");
    expect(alerta).toHaveTextContent("otro.pdf");
    expect(
      within(within(alerta).getByRole("list", { name: "Nombres esperados" })).getByText(
        NOMBRE_OFICIAL,
      ),
    ).toBeVisible();
    expect(service.requestUploadUrl).not.toHaveBeenCalled();

    await userEvent.click(within(alerta).getByRole("button", { name: "Cerrar" }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("cada fila tiene su botón Subir", async () => {
    renderPanel();
    await screen.findByText(NOMBRE_OFICIAL);
    expect(filas().getByRole("button", { name: "Subir" })).toBeVisible();

    fireEvent.change(screen.getByTestId("attachment-input-a-1"), {
      target: { files: [archivoDescargado()] },
    });

    await waitFor(() => expect(service.completeUpload).toHaveBeenCalledWith("t-1", "u-1"));
    expect(service.requestUploadUrl).toHaveBeenCalledWith("t-1", "a-1", expect.anything());
  });

  it("Subir en una fila rechaza el archivo de otro anexo sin llamar a la API", async () => {
    renderPanel();
    await screen.findByText(NOMBRE_OFICIAL);

    fireEvent.change(screen.getByTestId("attachment-input-a-1"), {
      target: { files: [new File(["hola"], "Bases.pdf")] },
    });

    expect(
      await screen.findByText(
        `«Bases.pdf» no corresponde a este anexo. Se esperaba «${NOMBRE_OFICIAL}».`,
      ),
    ).toBeVisible();
    expect(service.requestUploadUrl).not.toHaveBeenCalled();
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
    // No se deshabilita nada: un duplicado o un reintento no gastan cupo.
    expect(screen.getByRole("button", { name: "Subir" })).toBeEnabled();
  });

  it("el error de cupo se muestra en la fila y se puede reintentar", async () => {
    const user = userEvent.setup();
    const detalle = "Tu empresa alcanzó el tope de 100 subidas de anexos de este mes.";
    vi.mocked(service.requestUploadUrl).mockRejectedValueOnce(
      new ApiError(403, detalle, "quota_exceeded", { used: 100, limit: 100 }),
    );
    renderPanel();
    await screen.findByText(NOMBRE_OFICIAL);

    fireEvent.change(screen.getByTestId("attachment-input-a-1"), {
      target: { files: [archivoDescargado()] },
    });

    expect(await screen.findByText(detalle)).toBeVisible();
    await user.click(filas().getByRole("button", { name: "Reintentar" }));

    await waitFor(() => expect(service.completeUpload).toHaveBeenCalledWith("t-1", "u-1"));
    expect(service.requestUploadUrl).toHaveBeenCalledTimes(2);
  });

  it("muestra el progreso de la subida", async () => {
    vi.mocked(storage.putToStorage).mockImplementation(({ onProgress }) => {
      onProgress?.(0.5);
      return new Promise(() => {});
    });
    renderPanel();
    await screen.findByText(NOMBRE_OFICIAL);

    fireEvent.change(screen.getByTestId("attachment-input-a-1"), {
      target: { files: [archivoDescargado()] },
    });

    const barra = await screen.findByRole("progressbar");
    expect(barra).toHaveAttribute("aria-valuenow", "50");
    expect(screen.getByText("Subiendo 50 %")).toBeVisible();
  });
});
