import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, saveBlob } from "@/features/shared/api/client";
import * as service from "../../services/exportService";
import type { ExportJob } from "../../types";
import { ExportDownloadView } from "../ExportDownloadView";

vi.mock("@/features/shared/api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/shared/api/client")>()),
  saveBlob: vi.fn(),
}));

vi.mock("../../services/exportService", () => ({
  getExportJob: vi.fn(),
  downloadExportFile: vi.fn(),
}));

const PDF = new Blob(["%PDF"]);

function job(overrides: Partial<ExportJob> = {}): ExportJob {
  return {
    id: "j-1",
    status: "ready",
    format: "pdf",
    file_name: "licitacion-COT26.pdf",
    created_at: "2026-09-28T15:00:00Z",
    finished_at: "2026-09-28T15:00:20Z",
    expires_at: "2026-10-05T15:00:00Z",
    ...overrides,
  };
}

describe("ExportDownloadView", () => {
  beforeEach(() => {
    vi.mocked(saveBlob).mockReset();
    vi.mocked(service.getExportJob).mockReset();
    vi.mocked(service.downloadExportFile).mockReset();
  });

  it("un archivo listo se descarga con un clic", async () => {
    // Criterio 8: el enlace del correo lleva acá.
    const user = userEvent.setup();
    vi.mocked(service.getExportJob).mockResolvedValue(job());
    vi.mocked(service.downloadExportFile).mockResolvedValue({
      blob: PDF,
      filename: "licitacion-COT26.pdf",
    });
    render(<ExportDownloadView jobId="j-1" pollIntervalMs={10} />);

    expect(await screen.findByText("licitacion-COT26.pdf")).toBeInTheDocument();
    expect(screen.getByText(/disponible hasta el 05 oct 2026, 12:00/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /descargar pdf/i }));

    expect(service.downloadExportFile).toHaveBeenCalledWith("j-1");
    expect(saveBlob).toHaveBeenCalledWith(PDF, "licitacion-COT26.pdf");
  });

  it("si todavía se genera espera y luego ofrece la descarga", async () => {
    vi.mocked(service.getExportJob)
      .mockResolvedValueOnce(job({ status: "processing", finished_at: null }))
      .mockResolvedValue(job());
    render(<ExportDownloadView jobId="j-1" pollIntervalMs={10} />);

    // Con un sondeo de 10 ms el aviso dura poco: basta con que haya aparecido.
    await screen.findByText(/todavía se está generando/i);
    expect(
      await screen.findByRole("button", { name: /descargar pdf/i }),
    ).toBeInTheDocument();
  });

  it("si falló lo dice", async () => {
    vi.mocked(service.getExportJob).mockResolvedValue(job({ status: "failed" }));
    render(<ExportDownloadView jobId="j-1" pollIntervalMs={10} />);

    expect(await screen.findByRole("alert")).toHaveTextContent(/no se pudo generar/i);
    expect(screen.queryByRole("button", { name: /descargar/i })).not.toBeInTheDocument();
  });

  it("si venció al descargar lo explica", async () => {
    const user = userEvent.setup();
    vi.mocked(service.getExportJob).mockResolvedValue(job());
    vi.mocked(service.downloadExportFile).mockRejectedValue(
      new ApiError(410, "El archivo ya no está disponible: vence a los 7 días.", "export_expired"),
    );
    render(<ExportDownloadView jobId="j-1" pollIntervalMs={10} />);

    await user.click(await screen.findByRole("button", { name: /descargar pdf/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/vence a los 7 días/i);
    expect(saveBlob).not.toHaveBeenCalled();
  });

  it("una exportación ajena o inexistente no se muestra", async () => {
    vi.mocked(service.getExportJob).mockRejectedValue(new ApiError(404, "La exportación no existe."));
    render(<ExportDownloadView jobId="j-1" pollIntervalMs={10} />);

    expect(
      await screen.findByRole("heading", { name: /no encontramos esta exportación/i }),
    ).toBeInTheDocument();
  });

  it("ofrece volver a las licitaciones", async () => {
    vi.mocked(service.getExportJob).mockResolvedValue(job());
    render(<ExportDownloadView jobId="j-1" pollIntervalMs={10} />);

    await waitFor(() =>
      expect(screen.getByRole("link", { name: /volver a mis licitaciones/i })).toHaveAttribute(
        "href",
        "/matches",
      ),
    );
  });
});
