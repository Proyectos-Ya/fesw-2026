import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/features/shared/api/client";
import * as service from "../../services/tenderAttachmentsService";
import { buildTenderAttachments } from "../../test-utils";
import { useTenderAttachments } from "../useTenderAttachments";

vi.mock("../../services/tenderAttachmentsService", () => ({
  getTenderAttachments: vi.fn(),
}));

describe("useTenderAttachments", () => {
  beforeEach(() => {
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
});
