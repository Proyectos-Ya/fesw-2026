import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/features/shared/api/client";
import * as storage from "../../services/storageUpload";
import * as service from "../../services/tenderAttachmentsService";
import {
  buildAttachmentFile,
  buildOfficialAttachment,
  buildUploadTicket,
} from "../../test-utils";
import type { AttachmentFile } from "../../types";
import { useAttachmentUploads } from "../useAttachmentUploads";

vi.mock("../../services/tenderAttachmentsService", () => ({
  requestUploadUrl: vi.fn(),
  completeUpload: vi.fn(),
  deleteAttachmentFile: vi.fn(),
}));

// Se conserva `StorageUploadError` real: el hook decide el mensaje según su clase.
vi.mock("../../services/storageUpload", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../services/storageUpload")>()),
  putToStorage: vi.fn(),
}));

const SHA_HOLA = "b221d9dbb083a7f33428d7c2a3c3198ae925614d70210e28716ccaa7cd4ddb79";
const MAX = 52428800;

const XLSX = buildOfficialAttachment();
const BASES = buildOfficialAttachment({
  id: "a-2",
  mp_document_id: 1931003,
  name: "Bases.pdf",
  name_normalized: "bases.pdf",
  ext: "pdf",
});

const hola = (name = "anexo 3 composicion personalidad juridica (1).XLSX") =>
  new File(["hola"], name);

function setup(onChanged = vi.fn()) {
  const hook = renderHook(() => useAttachmentUploads("t-1", { maxSizeBytes: MAX, onChanged }));
  return { ...hook, onChanged };
}

describe("useAttachmentUploads", () => {
  beforeEach(() => {
    vi.mocked(service.requestUploadUrl).mockReset().mockResolvedValue(buildUploadTicket());
    vi.mocked(service.completeUpload).mockReset().mockResolvedValue(buildAttachmentFile());
    vi.mocked(service.deleteAttachmentFile).mockReset().mockResolvedValue(undefined);
    vi.mocked(storage.putToStorage).mockReset().mockResolvedValue(undefined);
  });

  it("sube un archivo: pide la URL, hace el PUT y confirma, en ese orden", async () => {
    const { result, onChanged } = setup();
    const file = hola();

    let ok = false;
    await act(async () => {
      ok = await result.current.uploadFile(XLSX, file);
    });

    expect(ok).toBe(true);
    expect(service.requestUploadUrl).toHaveBeenCalledWith("t-1", "a-1", {
      file_name: file.name,
      size_bytes: 4,
      mime: "",
      sha256: SHA_HOLA,
    });
    expect(storage.putToStorage).toHaveBeenCalledWith(
      expect.objectContaining({
        url: "https://almacen.test/put",
        method: "PUT",
        headers: buildUploadTicket().headers,
        body: file,
      }),
    );
    expect(service.completeUpload).toHaveBeenCalledWith("t-1", "u-1");
    const orden = [
      vi.mocked(service.requestUploadUrl).mock.invocationCallOrder[0],
      vi.mocked(storage.putToStorage).mock.invocationCallOrder[0],
      vi.mocked(service.completeUpload).mock.invocationCallOrder[0],
    ];
    expect(orden).toEqual([...orden].sort((a, b) => a - b));
    expect(onChanged).toHaveBeenCalledTimes(1);
    expect(result.current.rows).toEqual({});
  });

  it("si el archivo ya existe para la empresa no hace PUT ni confirma, pero avisa", async () => {
    vi.mocked(service.requestUploadUrl).mockResolvedValue({
      deduplicated: true,
      file: buildAttachmentFile(),
    });
    const { result, onChanged } = setup();

    await act(async () => {
      await result.current.uploadFile(XLSX, hola());
    });

    expect(storage.putToStorage).not.toHaveBeenCalled();
    expect(service.completeUpload).not.toHaveBeenCalled();
    expect(onChanged).toHaveBeenCalledTimes(1);
  });

  it("rechaza sin llamar a la API un archivo vacío", async () => {
    const { result, onChanged } = setup();

    await act(async () => {
      await result.current.uploadFile(XLSX, new File([], "anexo 3 composicion personalidad juridica.xlsx"));
    });

    expect(service.requestUploadUrl).not.toHaveBeenCalled();
    expect(result.current.rows["a-1"]).toMatchObject({
      phase: "error",
      message: "El archivo está vacío.",
    });
    expect(onChanged).not.toHaveBeenCalled();
  });

  it("rechaza sin llamar a la API un archivo de más de 50 MB", async () => {
    const { result } = setup();
    const enorme = hola();
    Object.defineProperty(enorme, "size", { value: MAX + 1 });

    await act(async () => {
      await result.current.uploadFile(XLSX, enorme);
    });

    expect(service.requestUploadUrl).not.toHaveBeenCalled();
    expect(result.current.rows["a-1"].message).toBe("El archivo supera el máximo de 50 MB.");
  });

  it("acepta un archivo con cualquier extensión sin validar nombre ni extensión", async () => {
    const { result } = setup();

    let ok = false;
    await act(async () => {
      ok = await result.current.uploadFile(XLSX, new File(["hola"], "Bases.pdf"));
    });

    expect(ok).toBe(true);
    expect(service.requestUploadUrl).toHaveBeenCalled();
  });

  it("acepta un archivo con nombre distinto pero extensión compatible", async () => {
    const { result } = setup();
    const file = new File(["hola"], "documento_descargado_1058043.xlsx");

    let ok = false;
    await act(async () => {
      ok = await result.current.uploadFile(XLSX, file);
    });

    expect(ok).toBe(true);
    expect(service.requestUploadUrl).toHaveBeenCalled();
  });

  it("si el PUT falla deja la fila en error con el archivo, y reintentar vuelve a pedir la URL", async () => {
    vi.mocked(storage.putToStorage).mockRejectedValueOnce(new storage.StorageUploadError(0));
    const { result, onChanged } = setup();
    const file = hola();

    await act(async () => {
      await result.current.uploadFile(XLSX, file);
    });

    expect(result.current.rows["a-1"]).toMatchObject({
      phase: "error",
      file,
      message: new storage.StorageUploadError(0).message,
    });
    expect(onChanged).not.toHaveBeenCalled();

    await act(async () => {
      await result.current.retry(XLSX);
    });

    expect(service.requestUploadUrl).toHaveBeenCalledTimes(2);
    expect(service.completeUpload).toHaveBeenCalledTimes(1);
    expect(result.current.rows).toEqual({});
    expect(onChanged).toHaveBeenCalledTimes(1);
  });

  it("si la verificación falla en el servidor muestra el error y refresca la lista", async () => {
    vi.mocked(service.completeUpload).mockRejectedValue(
      new ApiError(422, "El archivo que llegó no coincide.", "upload_verification_failed"),
    );
    const { result, onChanged } = setup();

    await act(async () => {
      await result.current.uploadFile(XLSX, hola());
    });

    expect(result.current.rows["a-1"]).toMatchObject({
      phase: "error",
      message: "El archivo que llegó no coincide.",
    });
    expect(onChanged).toHaveBeenCalledTimes(1);
  });

  it("al soltar dos archivos pide la URL del segundo solo cuando el primero terminó", async () => {
    let terminarPrimero: (file: AttachmentFile) => void = () => {};
    vi.mocked(service.completeUpload)
      .mockReturnValueOnce(new Promise((resolve) => (terminarPrimero = resolve)))
      .mockResolvedValue(buildAttachmentFile());
    const { result } = setup();
    const primero = hola();
    const segundo = new File(["hola"], "Bases.pdf");

    let terminado: Promise<void> = Promise.resolve();
    act(() => {
      terminado = result.current.uploadDropped([primero, segundo], [XLSX, BASES]);
    });
    await waitFor(() => expect(service.completeUpload).toHaveBeenCalledTimes(1));

    expect(service.requestUploadUrl).toHaveBeenCalledTimes(1);
    expect(result.current.rows["a-2"]).toMatchObject({ phase: "queued" });

    await act(async () => {
      terminarPrimero(buildAttachmentFile());
      await terminado;
    });

    expect(service.requestUploadUrl).toHaveBeenCalledTimes(2);
    expect(vi.mocked(service.completeUpload).mock.invocationCallOrder[0]).toBeLessThan(
      vi.mocked(service.requestUploadUrl).mock.invocationCallOrder[1],
    );
    expect(vi.mocked(service.requestUploadUrl).mock.calls[1][1]).toBe("a-2");
  });

  it("al soltar un archivo duplicado lo informa en rejections", async () => {
    const { result } = setup();

    await act(async () => {
      await result.current.uploadDropped(
        [
          new File(["x"], "Anexo 3 Composición personalidad juridica.xlsx"),
          new File(["y"], "anexo 3 composicion personalidad juridica (1).xlsx"),
        ],
        [XLSX],
      );
    });

    expect(result.current.rejections).toEqual([
      { fileName: "anexo 3 composicion personalidad juridica (1).xlsx", reason: "duplicate" },
    ]);

    act(() => result.current.dismissRejections());

    expect(result.current.rejections).toEqual([]);
  });

  it("borra el archivo de la fila y avisa", async () => {
    const { result, onChanged } = setup();
    const subido = buildOfficialAttachment({
      status: "stored",
      file: buildAttachmentFile({ id: "f-1" }),
    });

    await act(async () => {
      await result.current.removeFile(subido);
    });

    expect(service.deleteAttachmentFile).toHaveBeenCalledWith("t-1", "f-1");
    expect(onChanged).toHaveBeenCalledTimes(1);
  });

  it("si el borrado falla deja el error en la fila", async () => {
    vi.mocked(service.deleteAttachmentFile).mockRejectedValue(
      new ApiError(409, "El archivo ya está compartido.", "file_is_shared"),
    );
    const { result, onChanged } = setup();
    const subido = buildOfficialAttachment({ file: buildAttachmentFile() });

    await act(async () => {
      await result.current.removeFile(subido);
    });

    expect(result.current.rows["a-1"]).toMatchObject({
      phase: "error",
      message: "El archivo ya está compartido.",
    });
    expect(onChanged).not.toHaveBeenCalled();
  });

  it("el mensaje del error de cupo es el detalle del backend", async () => {
    const detalle = "Tu empresa alcanzó el tope de 100 subidas de anexos de este mes.";
    vi.mocked(service.requestUploadUrl).mockRejectedValue(
      new ApiError(403, detalle, "quota_exceeded", { used: 100, limit: 100 }),
    );
    const { result } = setup();

    await act(async () => {
      await result.current.uploadFile(XLSX, hola());
    });

    expect(result.current.rows["a-1"].message).toBe(detalle);
  });

  it("un 422 del cuerpo (sin code) y un error desconocido tienen mensajes genéricos", async () => {
    const { result } = setup();
    vi.mocked(service.requestUploadUrl).mockRejectedValueOnce(new ApiError(422, "x"));

    await act(async () => {
      await result.current.uploadFile(XLSX, hola());
    });
    expect(result.current.rows["a-1"].message).toBe("Los datos del archivo no son válidos.");

    vi.mocked(service.requestUploadUrl).mockRejectedValueOnce(new TypeError("boom"));
    await act(async () => {
      await result.current.uploadFile(XLSX, hola());
    });
    expect(result.current.rows["a-1"].message).toBe(
      "No se pudo subir el archivo. Inténtalo nuevamente.",
    );
  });

  it("no inicia una segunda subida de la misma fila mientras hay una en curso", async () => {
    let terminar: (file: AttachmentFile) => void = () => {};
    vi.mocked(service.completeUpload).mockReturnValueOnce(
      new Promise((resolve) => (terminar = resolve)),
    );
    const { result } = setup();

    let primera: Promise<boolean> = Promise.resolve(false);
    act(() => {
      primera = result.current.uploadFile(XLSX, hola());
    });
    await waitFor(() => expect(service.completeUpload).toHaveBeenCalled());
    let segunda = true;
    await act(async () => {
      segunda = await result.current.uploadFile(XLSX, hola());
    });

    expect(segunda).toBe(false);
    expect(service.requestUploadUrl).toHaveBeenCalledTimes(1);
    await act(async () => {
      terminar(buildAttachmentFile());
      await primera;
    });
  });
});
