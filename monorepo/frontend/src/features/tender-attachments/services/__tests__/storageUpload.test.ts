import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { putToStorage, StorageUploadError } from "../storageUpload";

class FakeXhr {
  static last: FakeXhr;
  method = "";
  url = "";
  withCredentials = true;
  status = 0;
  headers: Record<string, string> = {};
  sent: unknown = undefined;
  upload: { onprogress: ((event: unknown) => void) | null } = { onprogress: null };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onabort: (() => void) | null = null;

  constructor() {
    FakeXhr.last = this;
  }
  open(method: string, url: string) {
    this.method = method;
    this.url = url;
  }
  setRequestHeader(name: string, value: string) {
    this.headers[name] = value;
  }
  send(body: unknown) {
    this.sent = body;
  }
}

const HEADERS = {
  "x-amz-checksum-sha256": "siHZ27CDp/M0KNfCo8MZiuklYU1wIQ4ocWzKp81N23k=",
  "Content-Type": "application/pdf",
};

describe("putToStorage", () => {
  beforeEach(() => {
    vi.stubGlobal("XMLHttpRequest", FakeXhr);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function start(onProgress?: (fraction: number) => void) {
    const body = new File(["hola"], "a.pdf");
    const promise = putToStorage({
      url: "https://almacen.test/put",
      method: "PUT",
      headers: HEADERS,
      body,
      onProgress,
    });
    return { body, promise, xhr: FakeXhr.last };
  }

  it("hace PUT a la URL con exactamente las cabeceras recibidas, sin Authorization ni cookies", () => {
    const { body, xhr } = start();

    expect(xhr.method).toBe("PUT");
    expect(xhr.url).toBe("https://almacen.test/put");
    expect(xhr.headers).toEqual(HEADERS);
    expect(Object.keys(xhr.headers).map((h) => h.toLowerCase())).not.toContain("authorization");
    expect(xhr.withCredentials).toBe(false);
    expect(xhr.sent).toBe(body);
  });

  it("informa el progreso como fracción", () => {
    const onProgress = vi.fn();
    const { xhr } = start(onProgress);

    xhr.upload.onprogress?.({ lengthComputable: true, loaded: 2, total: 4 });

    expect(onProgress).toHaveBeenCalledWith(0.5);
  });

  it("ignora el progreso cuando no se puede calcular", () => {
    const onProgress = vi.fn();
    const { xhr } = start(onProgress);

    xhr.upload.onprogress?.({ lengthComputable: false, loaded: 2, total: 0 });

    expect(onProgress).not.toHaveBeenCalled();
  });

  it("resuelve con una respuesta 2xx", async () => {
    const { promise, xhr } = start();

    xhr.status = 200;
    xhr.onload?.();

    await expect(promise).resolves.toBeUndefined();
  });

  it("rechaza con el status cuando el almacenamiento responde un error", async () => {
    const { promise, xhr } = start();

    xhr.status = 403;
    xhr.onload?.();

    const error = await promise.catch((e: unknown) => e);
    expect(error).toBeInstanceOf(StorageUploadError);
    expect((error as StorageUploadError).status).toBe(403);
    expect((error as StorageUploadError).message).toContain("403");
  });

  it("un fallo de red da status 0", async () => {
    const { promise, xhr } = start();

    xhr.onerror?.();

    const error = await promise.catch((e: unknown) => e);
    expect(error).toBeInstanceOf(StorageUploadError);
    expect((error as StorageUploadError).status).toBe(0);
    expect((error as StorageUploadError).message).toMatch(/conectar/);
  });

  it("cancelar la subida también da status 0", async () => {
    const { promise, xhr } = start();

    xhr.onabort?.();

    await expect(promise).rejects.toMatchObject({ status: 0 });
  });
});
