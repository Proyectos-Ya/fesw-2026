import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/features/shared/api/client";
import * as service from "../../services/tenderAttachmentsService";
import { buildTenderAttachments } from "../../test-utils";
import { clearTenderAttachmentsCache, useTenderAttachments } from "../useTenderAttachments";

vi.mock("../../services/tenderAttachmentsService", () => ({
  getTenderAttachments: vi.fn(),
}));

describe("useTenderAttachments", () => {
  beforeEach(() => {
    clearTenderAttachmentsCache();
    vi.mocked(service.getTenderAttachments).mockReset();
  });

  it("carga los anexos al montar", async () => {
    vi.mocked(service.getTenderAttachments).mockResolvedValue(buildTenderAttachments());

    const { result } = renderHook(() => useTenderAttachments("t-1"));

    expect(result.current.state.status).toBe("loading");
    await waitFor(() => expect(result.current.state.status).toBe("ready"));
    expect(service.getTenderAttachments).toHaveBeenCalledWith("t-1");
  });

  it("expone el error de la API y permite reintentar", async () => {
    vi.mocked(service.getTenderAttachments)
      .mockRejectedValueOnce(new ApiError(500, "Falló el servidor"))
      .mockResolvedValueOnce(buildTenderAttachments());

    const { result } = renderHook(() => useTenderAttachments("t-1"));

    await waitFor(() => expect(result.current.state.status).toBe("error"));
    if (result.current.state.status === "error") {
      expect(result.current.state.message).toBe("Falló el servidor");
    }

    act(() => result.current.reload());

    expect(result.current.state.status).toBe("loading");
    await waitFor(() => expect(result.current.state.status).toBe("ready"));
  });

  it("ante un error desconocido muestra un mensaje genérico", async () => {
    vi.mocked(service.getTenderAttachments).mockRejectedValue(new TypeError("boom"));

    const { result } = renderHook(() => useTenderAttachments("t-1"));

    await waitFor(() => expect(result.current.state.status).toBe("error"));
    if (result.current.state.status === "error") {
      expect(result.current.state.message).toBe(
        "No se pudieron cargar los anexos de la licitación.",
      );
    }
  });

  it("refresh vuelve a pedir la lista sin pasar por loading", async () => {
    const nueva = buildTenderAttachments({ official: [] });
    vi.mocked(service.getTenderAttachments)
      .mockResolvedValueOnce(buildTenderAttachments())
      .mockResolvedValueOnce(nueva);
    const { result } = renderHook(() => useTenderAttachments("t-1"));
    await waitFor(() => expect(result.current.state.status).toBe("ready"));
    const estados: string[] = [];

    await act(async () => {
      const pendiente = result.current.refresh();
      estados.push(result.current.state.status);
      await pendiente;
    });

    estados.push(result.current.state.status);
    expect(estados).toEqual(["ready", "ready"]);
    expect(result.current.state).toEqual({ status: "ready", data: nueva });
    expect(service.getTenderAttachments).toHaveBeenCalledTimes(2);
  });

  it("si refresh falla conserva la lista que ya había", async () => {
    const original = buildTenderAttachments();
    vi.mocked(service.getTenderAttachments)
      .mockResolvedValueOnce(original)
      .mockRejectedValueOnce(new ApiError(500, "Falló el servidor"));
    const { result } = renderHook(() => useTenderAttachments("t-1"));
    await waitFor(() => expect(result.current.state.status).toBe("ready"));

    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.state).toEqual({ status: "ready", data: original });
  });

  it("refresh después de desmontar no actualiza el estado", async () => {
    let resolver: (data: ReturnType<typeof buildTenderAttachments>) => void = () => {};
    vi.mocked(service.getTenderAttachments)
      .mockResolvedValueOnce(buildTenderAttachments())
      .mockReturnValueOnce(new Promise((resolve) => (resolver = resolve)));
    const { result, unmount } = renderHook(() => useTenderAttachments("t-1"));
    await waitFor(() => expect(result.current.state.status).toBe("ready"));

    const pendiente = result.current.refresh();
    unmount();
    resolver(buildTenderAttachments({ official: [] }));

    await expect(pendiente).resolves.toBeUndefined();
  });
});
