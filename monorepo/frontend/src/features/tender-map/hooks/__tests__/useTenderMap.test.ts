import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/features/shared/api/client";
import { getTendersMap } from "../../services/tenderMapService";
import { buildTenderMapResult } from "../../test-utils";
import type { TenderMapResult } from "../../types";
import { useTenderMap } from "../useTenderMap";

vi.mock("../../services/tenderMapService", () => ({
  getTendersMap: vi.fn(),
}));

const mockGet = vi.mocked(getTendersMap);

describe("useTenderMap", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("sin zona no pide nada", () => {
    const { result } = renderHook(() => useTenderMap(null));

    expect(mockGet).not.toHaveBeenCalled();
    expect(result.current.loading).toBe(false);
    expect(result.current.data).toBeNull();
    expect(result.current.error).toBe(false);
  });

  it("carga los marcadores de la zona", async () => {
    const datos = buildTenderMapResult();
    mockGet.mockResolvedValue(datos);

    const { result } = renderHook(() => useTenderMap("Los Lagos"));

    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(mockGet).toHaveBeenCalledWith("Los Lagos");
    expect(result.current.data).toEqual(datos);
    expect(result.current.error).toBe(false);
  });

  it("un fallo deja el error y reintentar vuelve a pedir", async () => {
    mockGet.mockRejectedValueOnce(new ApiError(503, "caída"));
    mockGet.mockResolvedValueOnce(buildTenderMapResult());

    const { result } = renderHook(() => useTenderMap("Los Lagos"));
    await waitFor(() => expect(result.current.error).toBe(true));
    expect(result.current.data).toBeNull();

    act(() => result.current.retry());

    await waitFor(() => expect(result.current.data).not.toBeNull());
    expect(result.current.error).toBe(false);
    expect(mockGet).toHaveBeenCalledTimes(2);
  });

  it("al cambiar de zona pide la nueva y descarta la respuesta vieja", async () => {
    let resolverVieja: (valor: TenderMapResult) => void = () => {};
    mockGet.mockImplementationOnce(
      () => new Promise<TenderMapResult>((resolve) => (resolverVieja = resolve)),
    );
    const nueva = buildTenderMapResult({ region: "Ñuble", items: [] });
    mockGet.mockResolvedValueOnce(nueva);

    const { result, rerender } = renderHook(({ zona }) => useTenderMap(zona), {
      initialProps: { zona: "Los Lagos" },
    });
    rerender({ zona: "Ñuble" });
    await waitFor(() => expect(result.current.data).toEqual(nueva));

    await act(async () => resolverVieja(buildTenderMapResult()));

    expect(mockGet).toHaveBeenLastCalledWith("Ñuble");
    expect(result.current.data).toEqual(nueva);
  });
});
