import { describe, expect, it, vi } from "vitest";
import { R2Uploader } from "../r2-uploader";

describe("R2Uploader", () => {
  it("calcula sha256 coincidente con Web Crypto API", async () => {
    const encoder = new TextEncoder();
    const data = encoder.encode("contenido de prueba para hash");

    const sha256 = await R2Uploader.calculateSha256(data.buffer);
    expect(sha256).toBeDefined();
    expect(sha256).toHaveLength(64);
    expect(/^[a-f0-9]{64}$/.test(sha256)).toBe(true);
  });

  it("sube bytes a url PUT prefirmada con headers correctos", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
    });
    global.fetch = mockFetch;

    const data = new ArrayBuffer(8);
    const putUrl = "https://r2.cloudflarestorage.com/bucket/key?signed=true";
    const headers = {
      "x-amz-checksum-sha256": "dummy-hash",
      "Content-Type": "application/pdf",
    };

    await R2Uploader.uploadToR2(putUrl, data, headers);

    expect(mockFetch).toHaveBeenCalledWith(putUrl, {
      method: "PUT",
      headers,
      body: data,
    });
  });

  it("lanza error si la respuesta PUT no es exitosa", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      statusText: "Forbidden",
    });
    global.fetch = mockFetch;

    const data = new ArrayBuffer(8);
    await expect(
      R2Uploader.uploadToR2("https://r2.cloudflarestorage.com/bad", data, {})
    ).rejects.toThrow("Error en subida directa a R2: 403 Forbidden");
  });
});
