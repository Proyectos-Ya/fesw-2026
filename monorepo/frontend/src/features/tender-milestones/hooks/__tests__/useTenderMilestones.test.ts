import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/features/shared/api/client";
import * as service from "../../services/milestonesService";
import { buildMilestone, buildMilestoneList } from "../../test-utils";
import { MILESTONES_POLL_MS, useTenderMilestones } from "../useTenderMilestones";

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

  async function extraerCon(respuesta: ReturnType<typeof buildMilestoneList>) {
    vi.mocked(service.getTenderMilestones).mockResolvedValue(buildMilestoneList());
    vi.mocked(service.extractTenderMilestones).mockResolvedValue(respuesta);
    const { result } = renderHook(() => useTenderMilestones("t-1"));
    await waitFor(() => expect(result.current.state.status).toBe("ready"));
    await act(async () => {
      await result.current.extract();
    });
    return result.current.notice;
  }

  it("avisa cuando una base subida ya no está disponible y hay que volver a subirla", async () => {
    // En producción el disco del contenedor se borra en cada despliegue.
    const aviso = await extraerCon(buildMilestoneList({ unavailable_documents_count: 1 }));

    expect(aviso).toBe(
      "1 documento que subiste ya no está disponible. Vuelve a adjuntarlo en el asistente para extraer sus hitos.",
    );
  });

  it("habla en plural con varios documentos perdidos", async () => {
    const aviso = await extraerCon(buildMilestoneList({ unavailable_documents_count: 2 }));

    expect(aviso).toBe(
      "2 documentos que subiste ya no están disponibles. Vuelve a adjuntarlos en el asistente para extraer sus hitos.",
    );
  });

  it("si la IA leyó las bases pero no encontró plazos, lo dice", async () => {
    // Sin este aviso, la tabla con solo publicación y cierre parece un error.
    const aviso = await extraerCon(
      buildMilestoneList({ documents_count: 1, milestones: [buildMilestone()] }),
    );

    expect(aviso).toBe("La IA no encontró plazos en las bases adjuntas.");
  });

  it("avisa cuántas bases no se pudieron leer", async () => {
    const aviso = await extraerCon(
      buildMilestoneList({
        documents_count: 2,
        pending_documents_count: 1,
        failed_documents_count: 1,
        milestones: [buildMilestone({ source: "ia_documento" })],
      }),
    );

    expect(aviso).toBe("No se pudo leer 1 de las bases. Inténtalo de nuevo con el botón.");
  });

  it("si una base falló no dice que la IA no encontró plazos", async () => {
    const aviso = await extraerCon(
      buildMilestoneList({ documents_count: 2, pending_documents_count: 2, failed_documents_count: 2 }),
    );

    expect(aviso).toBe("No se pudieron leer 2 de las bases. Inténtalo de nuevo con el botón.");
  });

  it("si la IA encontró plazos no muestra ese aviso", async () => {
    const aviso = await extraerCon(
      buildMilestoneList({
        documents_count: 1,
        milestones: [buildMilestone(), buildMilestone({ id: "m-2", source: "ia_documento" })],
      }),
    );

    expect(aviso).toBeNull();
  });

  it("junta los avisos cuando hay más de uno", async () => {
    const aviso = await extraerCon(
      buildMilestoneList({
        documents_count: 1,
        discarded_count: 1,
        unavailable_documents_count: 1,
        milestones: [buildMilestone({ source: "ia_documento" })],
      }),
    );

    expect(aviso).toBe(
      "1 fecha no se pudo interpretar y se omitió. 1 documento que subiste ya no está disponible. Vuelve a adjuntarlo en el asistente para extraer sus hitos.",
    );
  });

  describe("extracción automática al subir las bases", () => {
    afterEach(() => {
      vi.useRealTimers();
    });

    it("mientras la IA lee las bases recarga sola hasta que termina", async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.mocked(service.getTenderMilestones)
        .mockResolvedValueOnce(buildMilestoneList({ documents_count: 1, extraction_status: "running" }))
        .mockResolvedValueOnce(
          buildMilestoneList({
            documents_count: 1,
            milestones: [buildMilestone(), buildMilestone({ id: "m-2", source: "ia_documento" })],
          }),
        );
      const { result } = renderHook(() => useTenderMilestones("t-1"));
      await waitFor(() => expect(result.current.state.status).toBe("ready"));

      await act(async () => {
        await vi.advanceTimersByTimeAsync(MILESTONES_POLL_MS);
      });

      await waitFor(() =>
        expect(result.current.state.status === "ready" && result.current.state.data.milestones).toHaveLength(2),
      );
      expect(result.current.notice).toBeNull();
      const llamadas = vi.mocked(service.getTenderMilestones).mock.calls.length;
      await act(async () => {
        await vi.advanceTimersByTimeAsync(MILESTONES_POLL_MS * 3);
      });
      expect(service.getTenderMilestones).toHaveBeenCalledTimes(llamadas);
    });

    it("si al terminar la IA no encontró plazos, lo avisa", async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.mocked(service.getTenderMilestones)
        .mockResolvedValueOnce(buildMilestoneList({ documents_count: 1, extraction_status: "running" }))
        .mockResolvedValueOnce(buildMilestoneList({ documents_count: 1 }));
      const { result } = renderHook(() => useTenderMilestones("t-1"));
      await waitFor(() => expect(result.current.state.status).toBe("ready"));

      await act(async () => {
        await vi.advanceTimersByTimeAsync(MILESTONES_POLL_MS);
      });

      await waitFor(() => expect(result.current.notice).toBe("La IA no encontró plazos en las bases adjuntas."));
    });

    it("si al terminar quedó una base sin leer, invita a reintentar", async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.mocked(service.getTenderMilestones)
        .mockResolvedValueOnce(buildMilestoneList({ documents_count: 2, extraction_status: "running" }))
        .mockResolvedValueOnce(
          buildMilestoneList({
            documents_count: 2,
            pending_documents_count: 1,
            milestones: [buildMilestone({ source: "ia_documento" })],
          }),
        );
      const { result } = renderHook(() => useTenderMilestones("t-1"));
      await waitFor(() => expect(result.current.state.status).toBe("ready"));

      await act(async () => {
        await vi.advanceTimersByTimeAsync(MILESTONES_POLL_MS);
      });

      await waitFor(() =>
        expect(result.current.notice).toBe("Queda 1 base sin leer. Inténtalo de nuevo con el botón."),
      );
    });

    it("si la extracción automática falla no dice que no encontró plazos", async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.mocked(service.getTenderMilestones)
        .mockResolvedValueOnce(buildMilestoneList({ documents_count: 1, extraction_status: "running" }))
        .mockResolvedValueOnce(buildMilestoneList({ documents_count: 1, extraction_status: "failed" }));
      const { result } = renderHook(() => useTenderMilestones("t-1"));
      await waitFor(() => expect(result.current.state.status).toBe("ready"));

      await act(async () => {
        await vi.advanceTimersByTimeAsync(MILESTONES_POLL_MS);
      });

      await waitFor(() =>
        expect(result.current.state.status === "ready" && result.current.state.data.extraction_status).toBe(
          "failed",
        ),
      );
      expect(result.current.notice).toBeNull();
    });

    it("recarga sin pasar por el estado de carga cuando cambian los documentos", async () => {
      vi.mocked(service.getTenderMilestones)
        .mockResolvedValueOnce(buildMilestoneList())
        .mockResolvedValueOnce(buildMilestoneList({ documents_count: 1, extraction_status: "running" }));
      const { result, rerender } = renderHook(({ key }) => useTenderMilestones("t-1", key), {
        initialProps: { key: 0 },
      });
      await waitFor(() => expect(result.current.state.status).toBe("ready"));

      rerender({ key: 1 });

      expect(result.current.state.status).toBe("ready");
      await waitFor(() =>
        expect(result.current.state.status === "ready" && result.current.state.data.extraction_status).toBe(
          "running",
        ),
      );
    });
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
