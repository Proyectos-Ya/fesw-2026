import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/features/shared/api/client";
import { getTenderDigest } from "../../services/tenderDigestService";
import { buildTenderDigest } from "../../test-utils";
import { useTenderDigest } from "../useTenderDigest";

vi.mock("../../services/tenderDigestService", () => ({
  getTenderDigest: vi.fn(),
}));

describe("useTenderDigest", () => {
  const digest = buildTenderDigest();

  beforeEach(() => {
    vi.mocked(getTenderDigest).mockReset();
    vi.mocked(getTenderDigest).mockResolvedValue(digest);
  });

  it("carga el digest exitosamente", async () => {
    const { result } = renderHook(() => useTenderDigest("t-1", "k-1"));

    expect(result.current.state.status).toBe("loading");

    await waitFor(() => {
      expect(result.current.state.status).toBe("ready");
    });

    if (result.current.state.status === "ready") {
      expect(result.current.state.data).toEqual(digest);
    }
    expect(getTenderDigest).toHaveBeenCalledWith("t-1");
  });

  it("maneja error en la carga inicial", async () => {
    vi.mocked(getTenderDigest).mockRejectedValue(new ApiError(500, "Error del servidor"));

    const { result } = renderHook(() => useTenderDigest("t-1", "k-1"));

    await waitFor(() => {
      expect(result.current.state.status).toBe("error");
    });

    if (result.current.state.status === "error") {
      expect(result.current.state.message).toBe("Error del servidor");
    }
  });

  it("conserva datos y no vuelve a loading cuando refreshKey cambia", async () => {
    const { result, rerender } = renderHook(
      ({ rk }) => useTenderDigest("t-1", rk),
      { initialProps: { rk: "k-1" } }
    );

    await waitFor(() => {
      expect(result.current.state.status).toBe("ready");
    });

    const digestActualizado = buildTenderDigest({ version: 2 });
    vi.mocked(getTenderDigest).mockResolvedValue(digestActualizado);

    rerender({ rk: "k-2" });

    // El estado sigue en ready durante la recarga silenciosa
    expect(result.current.state.status).toBe("ready");

    await waitFor(() => {
      if (result.current.state.status === "ready") {
        expect(result.current.state.data.version).toBe(2);
      }
    });

    expect(getTenderDigest).toHaveBeenCalledTimes(2);
  });

  it("permite recargar con reload pasando a loading", async () => {
    const { result } = renderHook(() => useTenderDigest("t-1", "k-1"));

    await waitFor(() => {
      expect(result.current.state.status).toBe("ready");
    });

    act(() => {
      result.current.reload();
    });

    expect(result.current.state.status).toBe("loading");

    await waitFor(() => {
      expect(result.current.state.status).toBe("ready");
    });
  });
});
