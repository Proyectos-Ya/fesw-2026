import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, saveBlob } from "@/features/shared/api/client";
import * as service from "../../services/exportService";
import type { ExportJob } from "../../types";
import { useTenderExport } from "../useTenderExport";

vi.mock("@/features/shared/api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/shared/api/client")>()),
  saveBlob: vi.fn(),
}));

vi.mock("../../services/exportService", () => ({
  exportTender: vi.fn(),
  getExportJob: vi.fn(),
  downloadExportFile: vi.fn(),
}));

const PDF = new Blob(["%PDF"]);
const POLL = 10;

function job(status: ExportJob["status"]): ExportJob {
  return {
    id: "j-1",
    status,
    format: "pdf",
    file_name: "licitacion-COT26.pdf",
    created_at: "2026-09-28T15:00:00Z",
    finished_at: null,
    expires_at: "2026-10-05T15:00:00Z",
  };
}

describe("useTenderExport", () => {
  beforeEach(() => {
    vi.mocked(saveBlob).mockReset();
    vi.mocked(service.exportTender).mockReset();
    vi.mocked(service.getExportJob).mockReset();
    vi.mocked(service.downloadExportFile).mockReset();
  });

  it("si el archivo llega a tiempo lo descarga de inmediato", async () => {
    vi.mocked(service.exportTender).mockResolvedValue({
      kind: "file",
      blob: PDF,
      filename: "licitacion-COT26.pdf",
    });
    const { result } = renderHook(() => useTenderExport("t-1", { pollIntervalMs: POLL }));

    await act(() => result.current.exportAs("pdf", []));

    expect(saveBlob).toHaveBeenCalledWith(PDF, "licitacion-COT26.pdf");
    expect(result.current.state).toEqual({ status: "done", format: "pdf" });
  });

  it("mientras genera informa el formato", async () => {
    let terminar: (v: Awaited<ReturnType<typeof service.exportTender>>) => void = () => {};
    vi.mocked(service.exportTender).mockReturnValue(new Promise((r) => (terminar = r)));
    const { result } = renderHook(() => useTenderExport("t-1", { pollIntervalMs: POLL }));

    act(() => void result.current.exportAs("xlsx", ["hitos"]));

    expect(result.current.state).toEqual({ status: "generating", format: "xlsx" });
    await act(async () => terminar({ kind: "file", blob: PDF, filename: "a.xlsx" }));
  });

  it("si tarda muestra el aviso y descarga solo cuando está listo", async () => {
    // Criterios 8 y 9.
    vi.mocked(service.exportTender).mockResolvedValue({
      kind: "queued",
      jobId: "j-1",
      message: "Te avisaremos por correo cuando esté listo.",
    });
    vi.mocked(service.getExportJob)
      .mockResolvedValueOnce(job("processing"))
      .mockResolvedValue(job("ready"));
    vi.mocked(service.downloadExportFile).mockResolvedValue({
      blob: PDF,
      filename: "licitacion-COT26.pdf",
    });
    const { result } = renderHook(() => useTenderExport("t-1", { pollIntervalMs: POLL }));

    await act(() => result.current.exportAs("pdf", []));

    expect(result.current.state).toEqual({
      status: "queued",
      format: "pdf",
      message: "Te avisaremos por correo cuando esté listo.",
    });
    await waitFor(() => expect(saveBlob).toHaveBeenCalledWith(PDF, "licitacion-COT26.pdf"));
    expect(service.downloadExportFile).toHaveBeenCalledWith("j-1");
    expect(result.current.state).toEqual({ status: "done", format: "pdf" });
  });

  it("si la generación en segundo plano falla lo informa", async () => {
    vi.mocked(service.exportTender).mockResolvedValue({
      kind: "queued",
      jobId: "j-1",
      message: "…",
    });
    vi.mocked(service.getExportJob).mockResolvedValue(job("failed"));
    const { result } = renderHook(() => useTenderExport("t-1", { pollIntervalMs: POLL }));

    await act(() => result.current.exportAs("pdf", []));

    await waitFor(() => expect(result.current.state.status).toBe("error"));
    expect(saveBlob).not.toHaveBeenCalled();
  });

  it("un error de red al consultar no corta la espera", async () => {
    vi.mocked(service.exportTender).mockResolvedValue({ kind: "queued", jobId: "j-1", message: "…" });
    vi.mocked(service.getExportJob)
      .mockRejectedValueOnce(new Error("red caída"))
      .mockResolvedValue(job("ready"));
    vi.mocked(service.downloadExportFile).mockResolvedValue({ blob: PDF, filename: "a.pdf" });
    const { result } = renderHook(() => useTenderExport("t-1", { pollIntervalMs: POLL }));

    await act(() => result.current.exportAs("pdf", []));

    await waitFor(() => expect(result.current.state.status).toBe("done"));
  });

  it("si la exportación falla muestra el mensaje del backend", async () => {
    vi.mocked(service.exportTender).mockRejectedValue(
      new ApiError(403, "Tu rol en esta empresa no permite exportar licitaciones."),
    );
    const { result } = renderHook(() => useTenderExport("t-1", { pollIntervalMs: POLL }));

    await act(() => result.current.exportAs("pdf", []));

    expect(result.current.state).toEqual({
      status: "error",
      message: "Tu rol en esta empresa no permite exportar licitaciones.",
    });
  });

  it("deja de consultar al desmontarse", async () => {
    vi.mocked(service.exportTender).mockResolvedValue({ kind: "queued", jobId: "j-1", message: "…" });
    vi.mocked(service.getExportJob).mockResolvedValue(job("processing"));
    const { result, unmount } = renderHook(() =>
      useTenderExport("t-1", { pollIntervalMs: POLL }),
    );
    await act(() => result.current.exportAs("pdf", []));
    await waitFor(() => expect(service.getExportJob).toHaveBeenCalled());

    unmount();
    const llamadas = vi.mocked(service.getExportJob).mock.calls.length;
    await new Promise((r) => setTimeout(r, POLL * 5));

    expect(vi.mocked(service.getExportJob).mock.calls.length).toBe(llamadas);
  });
});
