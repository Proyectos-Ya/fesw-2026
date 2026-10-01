import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/features/shared/api/client";
import * as service from "../../services/proposalService";
import { ProposalView } from "../ProposalView";
import { requisito, vista } from "../../testing/fixtures";

vi.mock("../../services/proposalService", () => ({
  getProposal: vi.fn(),
  startFeasibility: vi.fn(),
  answerProposalQuestion: vi.fn(),
  decideDiscrepancy: vi.fn(),
  resumeProposal: vi.fn(),
  generateProposal: vi.fn(),
  regenerateProposal: vi.fn(),
  downloadTechnicalDocument: vi.fn(),
}));

vi.mock("@/features/matches/services/tenderService", () => ({
  getTenderDetail: vi.fn().mockResolvedValue({
    tender: { id: "t-1", code: "657-70-COT26", name: "Capacitación PAC" },
    is_closed: false,
    score_pct: null,
  }),
}));

vi.mock("../ProposalAttachments", () => ({ ProposalAttachments: () => null }));

const permiso = { activo: { id: "w" } as object | null, puede: true };
vi.mock("@/features/workspaces/WorkspaceContext", () => ({
  useWorkspace: () => ({
    activeWorkspace: permiso.activo,
    hasPermission: () => permiso.puede,
  }),
}));

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), back: vi.fn() }) }));

const svc = vi.mocked(service);

beforeEach(() => {
  vi.clearAllMocks();
  permiso.activo = { id: "w" };
  permiso.puede = true;
});

describe("ProposalView", () => {
  it("sin postulación ofrece iniciarla y muestra la etapa mientras analiza (CA6)", async () => {
    svc.getProposal.mockRejectedValueOnce(new ApiError(404, "x"));
    svc.startFeasibility.mockImplementation(() => new Promise(() => {}));
    render(<ProposalView tenderId="t-1" />);

    await userEvent.click(
      await screen.findByRole("button", { name: /Iniciar análisis de factibilidad/ }),
    );

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Analizando bases y experiencia",
    );
    expect(svc.startFeasibility).toHaveBeenCalledWith("t-1");
  });

  it("muestra el encabezado con la licitación", async () => {
    svc.getProposal.mockResolvedValue(vista());
    render(<ProposalView tenderId="t-1" />);

    expect(await screen.findByRole("heading", { name: "Capacitación PAC" })).toBeInTheDocument();
  });

  it("en factibilidad responde y recarga", async () => {
    svc.getProposal.mockResolvedValue(vista());
    svc.answerProposalQuestion.mockResolvedValue(vista());
    render(<ProposalView tenderId="t-1" />);

    const botones = await screen.findAllByRole("button", { name: "Sí" });
    await userEvent.click(botones[0]);

    await waitFor(() => expect(svc.getProposal).toHaveBeenCalledTimes(2));
    expect(svc.answerProposalQuestion).toHaveBeenCalledWith("t-1", "q-sec", "Sí");
  });

  it("en pausa abre el aviso de discrepancia (CA7)", async () => {
    svc.getProposal.mockResolvedValue(
      vista({
        status: "PAUSED",
        paused_requirement_id: "req-1",
        requirements: [requisito({ status: "no_cumple" })],
      }),
    );
    render(<ProposalView tenderId="t-1" />);

    expect(await screen.findByRole("dialog")).toHaveTextContent("Recomendamos no postular");
  });

  it("detenida ofrece reanudar (CA9)", async () => {
    svc.getProposal.mockResolvedValue(
      vista({ status: "STOPPED", requirements: [requisito({ status: "no_cumple" })] }),
    );
    svc.resumeProposal.mockResolvedValue(vista());
    render(<ProposalView tenderId="t-1" />);

    await userEvent.click(await screen.findByRole("button", { name: "Reanudar" }));

    expect(svc.resumeProposal).toHaveBeenCalledWith("t-1");
  });

  it("vencida avisa y no deja avanzar", async () => {
    svc.getProposal.mockResolvedValue(vista({ is_expired: true }));
    render(<ProposalView tenderId="t-1" />);

    expect(await screen.findByText(/cerrada para postulaciones/)).toBeInTheDocument();
    for (const boton of screen.getAllByRole("button", { name: "Sí" })) {
      expect(boton).toBeDisabled();
    }
  });

  it("un error de una acción se muestra sin perder la vista", async () => {
    svc.getProposal.mockResolvedValue(vista({ requirements: [requisito({ status: "cumple" })] }));
    svc.generateProposal.mockRejectedValue(
      new ApiError(502, "No fue posible redactar el borrador en este momento."),
    );
    render(<ProposalView tenderId="t-1" />);

    await userEvent.click(await screen.findByRole("button", { name: /Redactar borrador/ }));

    expect(await screen.findByText(/No fue posible redactar/)).toBeInTheDocument();
    expect(screen.getByText("Exigencias evaluadas")).toBeInTheDocument();
  });

  it("sin permiso no ofrece iniciar", async () => {
    permiso.puede = false;
    svc.getProposal.mockRejectedValueOnce(new ApiError(404, "x"));
    render(<ProposalView tenderId="t-1" />);

    expect(await screen.findByText(/Solo quienes pueden generar/)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Iniciar análisis de factibilidad/ }),
    ).not.toBeInTheDocument();
  });
});
