import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/features/shared/api/client";
import * as service from "../../services/proposalService";
import { useProposal } from "../useProposal";
import { vista } from "../../testing/fixtures";

vi.mock("../../services/proposalService", () => ({
  getProposal: vi.fn(),
  startFeasibility: vi.fn(),
  reanalyzeProposal: vi.fn(),
  answerProposalQuestion: vi.fn(),
  decideDiscrepancy: vi.fn(),
  resumeProposal: vi.fn(),
  generateProposal: vi.fn(),
  regenerateProposal: vi.fn(),
  requestTechnicalDocument: vi.fn(),
  syncProposalAnswers: vi.fn(),
  downloadTechnicalDocument: vi.fn(),
}));

const svc = vi.mocked(service);

beforeEach(() => {
  vi.resetAllMocks();
});

async function montado() {
  const hook = renderHook(() => useProposal("t-1"));
  await waitFor(() => expect(hook.result.current.state.kind).not.toBe("loading"));
  return hook;
}

describe("useProposal", () => {
  it("carga el borrador existente", async () => {
    svc.getProposal.mockResolvedValue(vista());

    const { result } = await montado();

    expect(result.current.state).toEqual({ kind: "ready", view: vista() });
  });

  it("sin borrador queda sin iniciar", async () => {
    svc.getProposal.mockRejectedValue(new ApiError(404, "No hay postulación"));

    const { result } = await montado();

    expect(result.current.state).toEqual({ kind: "not-started" });
  });

  it("otro error se muestra", async () => {
    svc.getProposal.mockRejectedValue(new ApiError(500, "Falla"));

    const { result } = await montado();

    expect(result.current.state).toEqual({ kind: "error", message: "Falla" });
  });

  it("iniciar muestra la etapa de análisis y luego recarga (CA6)", async () => {
    svc.getProposal.mockRejectedValueOnce(new ApiError(404, "x"));
    let terminar: () => void = () => {};
    svc.startFeasibility.mockImplementation(
      () => new Promise((resolve) => (terminar = () => resolve(vista()))),
    );
    const { result } = await montado();
    svc.getProposal.mockResolvedValue(vista());

    let pendiente: Promise<void> = Promise.resolve();
    act(() => {
      pendiente = result.current.start();
    });
    await waitFor(() => expect(result.current.stage).toBe("analyzing"));

    await act(async () => {
      terminar();
      await pendiente;
    });

    expect(result.current.stage).toBeNull();
    expect(result.current.state).toEqual({ kind: "ready", view: vista() });
  });

  it("redactar muestra la etapa de redacción (CA6)", async () => {
    svc.getProposal.mockResolvedValue(vista());
    let terminar: () => void = () => {};
    svc.generateProposal.mockImplementation(
      () => new Promise((resolve) => (terminar = () => resolve(vista()))),
    );
    const { result } = await montado();

    let pendiente: Promise<void> = Promise.resolve();
    act(() => {
      pendiente = result.current.generate();
    });
    await waitFor(() => expect(result.current.stage).toBe("drafting"));
    await act(async () => {
      terminar();
      await pendiente;
    });

    expect(result.current.stage).toBeNull();
  });

  it("regenerar muestra su propia etapa y confirma al terminar", async () => {
    svc.getProposal.mockResolvedValue(vista({ status: "READY" }));
    let terminar: () => void = () => {};
    svc.regenerateProposal.mockImplementation(
      () => new Promise((resolve) => (terminar = () => resolve(vista()))),
    );
    const { result } = await montado();

    let pendiente: Promise<void> = Promise.resolve();
    act(() => {
      pendiente = result.current.regenerate("Más formal");
    });
    await waitFor(() => expect(result.current.stage).toBe("regenerating"));
    await act(async () => {
      terminar();
      await pendiente;
    });

    expect(svc.regenerateProposal).toHaveBeenCalledWith("t-1", "Más formal");
    expect(result.current.stage).toBeNull();
    expect(result.current.toast?.message).toBe("Borrador regenerado con tus instrucciones.");
  });

  it("si regenerar falla no confirma", async () => {
    svc.getProposal.mockResolvedValue(vista({ status: "READY" }));
    svc.regenerateProposal.mockRejectedValue(new ApiError(502, "Falla"));
    const { result } = await montado();

    await act(() => result.current.regenerate("Más formal"));

    expect(result.current.actionError).toBe("Falla");
    expect(result.current.toast).toBeNull();
  });

  it("mientras responde dice qué opción se pulsó, y confirma al terminar", async () => {
    svc.getProposal.mockResolvedValue(vista());
    let terminar: () => void = () => {};
    svc.answerProposalQuestion.mockImplementation(
      () => new Promise((resolve) => (terminar = () => resolve(vista()))),
    );
    const { result } = await montado();

    let pendiente: Promise<void> = Promise.resolve();
    act(() => {
      pendiente = result.current.answer("q-sec", "Sí");
    });
    await waitFor(() =>
      expect(result.current.answering).toEqual({ questionId: "q-sec", label: "Sí" }),
    );
    await act(async () => {
      terminar();
      await pendiente;
    });

    expect(result.current.answering).toBeNull();
    expect(result.current.toast?.message).toBe("Respuesta guardada.");
    act(() => result.current.clearToast());
    expect(result.current.toast).toBeNull();
  });

  it("pedir el documento técnico muestra la etapa de redacción", async () => {
    svc.getProposal.mockResolvedValue(vista({ status: "READY" }));
    svc.requestTechnicalDocument.mockResolvedValue(vista());
    const { result } = await montado();

    await act(() => result.current.requestTechnical());

    expect(svc.requestTechnicalDocument).toHaveBeenCalledWith("t-1");
  });

  it("aplicar las respuestas cambiadas llama al servicio y recarga", async () => {
    svc.getProposal.mockResolvedValue(vista({ changed_requirement_ids: ["req-1"] }));
    svc.syncProposalAnswers.mockResolvedValue(vista());
    const { result } = await montado();

    await act(() => result.current.syncAnswers());

    expect(svc.syncProposalAnswers).toHaveBeenCalledWith("t-1");
    expect(svc.getProposal).toHaveBeenCalledTimes(2);
  });

  it("responder llama al servicio y recarga", async () => {
    svc.getProposal.mockResolvedValue(vista());
    svc.answerProposalQuestion.mockResolvedValue(vista());
    const { result } = await montado();

    await act(() => result.current.answer("q-sec", "No"));

    expect(svc.answerProposalQuestion).toHaveBeenCalledWith("t-1", "q-sec", "No");
    expect(svc.getProposal).toHaveBeenCalledTimes(2);
  });

  it("un error de una acción queda en actionError y no rompe la vista", async () => {
    svc.getProposal.mockResolvedValue(vista());
    svc.decideDiscrepancy.mockRejectedValue(
      new ApiError(409, "La pausa ya no es esa exigencia"),
    );
    const { result } = await montado();

    await act(() => result.current.decide("req-1", "continue"));

    expect(result.current.actionError).toBe("La pausa ya no es esa exigencia");
    expect(result.current.state.kind).toBe("ready");
  });

  it("volver a analizar sin cambios lo avisa y mantiene el borrador", async () => {
    svc.getProposal.mockResolvedValue(vista({ status: "READY" }));
    svc.reanalyzeProposal.mockResolvedValue(vista({ status: "READY" }));
    const { result } = await montado();

    await act(() => result.current.reanalyze());

    expect(result.current.notice).toMatch(/No hubo cambios/);
  });

  it("volver a analizar con cambios no deja aviso", async () => {
    svc.getProposal.mockResolvedValue(vista({ status: "READY" }));
    svc.reanalyzeProposal.mockResolvedValue(
      vista({ updated_at: "2026-10-02T10:00:00Z" }),
    );
    const { result } = await montado();

    await act(() => result.current.reanalyze());

    expect(svc.reanalyzeProposal).toHaveBeenCalledWith("t-1");
    expect(result.current.notice).toBeNull();
  });

  it("descarga el documento técnico con su nombre", async () => {
    svc.getProposal.mockResolvedValue(vista());
    svc.downloadTechnicalDocument.mockResolvedValue({
      blob: new Blob(["PK"]),
      filename: "documento-tecnico-1.docx",
    });
    const crear = vi.fn(() => "blob:url");
    const revocar = vi.fn();
    vi.stubGlobal("URL", { ...URL, createObjectURL: crear, revokeObjectURL: revocar });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    const { result } = await montado();

    await act(() => result.current.download());

    expect(click).toHaveBeenCalled();
    expect(revocar).toHaveBeenCalledWith("blob:url");
    expect(result.current.toast?.message).toBe("Documento descargado.");
    vi.unstubAllGlobals();
  });
});
