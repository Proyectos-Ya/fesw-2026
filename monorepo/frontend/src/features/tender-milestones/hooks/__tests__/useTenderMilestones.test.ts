import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/features/shared/api/client";
import * as service from "../../services/milestonesService";
import { buildMilestone, buildMilestoneList } from "../../test-utils";
import { useTenderMilestones } from "../useTenderMilestones";

vi.mock("../../services/milestonesService", () => ({
  getTenderMilestones: vi.fn(),
  extractTenderMilestones: vi.fn(),
}));

describe("useTenderMilestones", () => {
  beforeEach(() => {
    vi.mocked(service.getTenderMilestones).mockReset();
    vi.mocked(service.extractTenderMilestones).mockReset();
  });

  it("carga los hitos al montar", async () => {
    vi.mocked(service.getTenderMilestones).mockResolvedValue(buildMilestoneList());

    const { result } = renderHook(() => useTenderMilestones("t-1"));

    expect(result.current.state.status).toBe("loading");
    await waitFor(() => expect(result.current.state.status).toBe("ready"));
    expect(service.getTenderMilestones).toHaveBeenCalledWith("t-1");
  });

  it("expone el error de carga y permite reintentar", async () => {
    vi.mocked(service.getTenderMilestones)
      .mockRejectedValueOnce(new ApiError(500, "Falló el servidor"))
      .mockResolvedValueOnce(buildMilestoneList());

    const { result } = renderHook(() => useTenderMilestones("t-1"));

    await waitFor(() => expect(result.current.state.status).toBe("error"));
    if (result.current.state.status === "error") {
      expect(result.current.state.message).toBe("Falló el servidor");
    }

    act(() => result.current.reload());

    await waitFor(() => expect(result.current.state.status).toBe("ready"));
  });

  it("al extraer reemplaza los hitos y avisa cuántas fechas se descartaron", async () => {
    vi.mocked(service.getTenderMilestones).mockResolvedValue(buildMilestoneList());
    vi.mocked(service.extractTenderMilestones).mockResolvedValue(
      buildMilestoneList({
        milestones: [buildMilestone(), buildMilestone({ id: "m-2", kind: "visita_tecnica" })],
        discarded_count: 2,
      }),
    );
    const { result } = renderHook(() => useTenderMilestones("t-1"));
    await waitFor(() => expect(result.current.state.status).toBe("ready"));

    await act(async () => {
      await result.current.extract();
    });

    expect(result.current.state.status === "ready" && result.current.state.data.milestones).toHaveLength(2);
    expect(result.current.notice).toBe("2 fechas no se pudieron interpretar y se omitieron.");
    expect(result.current.isExtracting).toBe(false);
  });

  it("refresh recarga sin pasar por el estado de carga", async () => {
    vi.mocked(service.getTenderMilestones)
      .mockResolvedValueOnce(buildMilestoneList())
      .mockResolvedValueOnce(
        buildMilestoneList({ milestones: [buildMilestone({ synced_providers: ["google"] })] }),
      );
    const { result } = renderHook(() => useTenderMilestones("t-1"));
    await waitFor(() => expect(result.current.state.status).toBe("ready"));
    const estados: string[] = [];

    await act(async () => {
      const promesa = result.current.refresh();
      estados.push(result.current.state.status);
      await promesa;
    });

    expect(estados).toEqual(["ready"]);
    expect(
      result.current.state.status === "ready" && result.current.state.data.milestones[0].synced_providers,
    ).toEqual(["google"]);
  });

  it("si la extracción falla conserva los hitos y muestra el error", async () => {
    vi.mocked(service.getTenderMilestones).mockResolvedValue(buildMilestoneList());
    vi.mocked(service.extractTenderMilestones).mockRejectedValue(
      new ApiError(503, "No se pudieron extraer los hitos de las bases en este momento."),
    );
    const { result } = renderHook(() => useTenderMilestones("t-1"));
    await waitFor(() => expect(result.current.state.status).toBe("ready"));

    await act(async () => {
      await result.current.extract();
    });

    expect(result.current.state.status).toBe("ready");
    expect(result.current.extractError).toBe(
      "No se pudieron extraer los hitos de las bases en este momento.",
    );
  });
});
