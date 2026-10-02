import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiDownload, apiFetch } from "@/features/shared/api/client";
import { downloadExportFile, exportTender, getExportJob } from "../exportService";

vi.mock("@/features/shared/api/client", () => ({
  apiDownload: vi.fn(),
  apiFetch: vi.fn(),
}));

const PDF = new Blob(["%PDF"], { type: "application/pdf" });

describe("exportService", () => {
  beforeEach(() => {
    vi.mocked(apiDownload).mockReset();
    vi.mocked(apiFetch).mockReset();
  });

  it("pide la exportación con el formato y las secciones", async () => {
    vi.mocked(apiDownload).mockResolvedValue({ kind: "file", blob: PDF, filename: "x.xlsx" });

    await exportTender("t-1", "xlsx", ["hitos", "montos"]);

    expect(apiDownload).toHaveBeenCalledWith("/tenders/t-1/exports", {
      method: "POST",
      body: JSON.stringify({ format: "xlsx", sections: ["hitos", "montos"] }),
    });
  });

  it("si llega el archivo lo devuelve con su nombre", async () => {
    vi.mocked(apiDownload).mockResolvedValue({
      kind: "file",
      blob: PDF,
      filename: "licitacion-COT26.pdf",
    });

    await expect(exportTender("t-1", "pdf", [])).resolves.toEqual({
      kind: "file",
      blob: PDF,
      filename: "licitacion-COT26.pdf",
    });
  });

  it("sin nombre del backend usa uno por defecto con la extensión correcta", async () => {
    vi.mocked(apiDownload).mockResolvedValue({ kind: "file", blob: PDF, filename: null });

    const resultado = await exportTender("t-1", "xlsx", ["hitos"]);

    expect(resultado).toMatchObject({ filename: "licitacion.xlsx" });
  });

  it("si pasó a segundo plano devuelve el trabajo y el aviso", async () => {
    vi.mocked(apiDownload).mockResolvedValue({
      kind: "accepted",
      body: { job_id: "j-1", status: "processing", message: "Te avisaremos por correo." },
    });

    await expect(exportTender("t-1", "pdf", [])).resolves.toEqual({
      kind: "queued",
      jobId: "j-1",
      message: "Te avisaremos por correo.",
    });
  });

  it("un 202 con un cuerpo inesperado es un error", async () => {
    vi.mocked(apiDownload).mockResolvedValue({ kind: "accepted", body: { raro: true } });

    await expect(exportTender("t-1", "pdf", [])).rejects.toThrow();
  });

  it("consulta el estado del trabajo", async () => {
    await getExportJob("j-1");

    expect(apiFetch).toHaveBeenCalledWith("/exports/j-1");
  });

  it("descarga el archivo terminado", async () => {
    vi.mocked(apiDownload).mockResolvedValue({ kind: "file", blob: PDF, filename: "a.pdf" });

    await expect(downloadExportFile("j/1")).resolves.toEqual({ blob: PDF, filename: "a.pdf" });
    expect(apiDownload).toHaveBeenCalledWith("/exports/j%2F1/file");
  });
});
