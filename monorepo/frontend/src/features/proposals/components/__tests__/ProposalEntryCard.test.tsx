import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/features/shared/api/client";
import * as service from "../../services/proposalService";
import { ProposalEntryCard } from "../ProposalEntryCard";
import { requisito, vista } from "../../testing/fixtures";

vi.mock("../../services/proposalService", () => ({ getProposal: vi.fn() }));

const permiso = { puede: true };
vi.mock("@/features/workspaces/WorkspaceContext", () => ({
  useWorkspace: () => ({ activeWorkspace: { id: "w" }, hasPermission: () => permiso.puede }),
}));

const svc = vi.mocked(service);

beforeEach(() => {
  vi.clearAllMocks();
  permiso.puede = true;
});

describe("ProposalEntryCard", () => {
  it("sin postulación ofrece generarla", async () => {
    svc.getProposal.mockRejectedValue(new ApiError(404, "x"));
    render(<ProposalEntryCard tenderId="t-1" isClosed={false} />);

    const enlace = await screen.findByRole("link", { name: "Generar postulación" });
    expect(enlace).toHaveAttribute("href", "/matches/t-1/postulacion");
  });

  it("cerrada y sin postulación no ofrece generarla", async () => {
    svc.getProposal.mockRejectedValue(new ApiError(404, "x"));
    render(<ProposalEntryCard tenderId="t-1" isClosed />);

    expect(await screen.findByText(/cerrada para postulaciones/)).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("en curso dice cuántas preguntas quedan", async () => {
    svc.getProposal.mockResolvedValue(vista());
    render(<ProposalEntryCard tenderId="t-1" isClosed={false} />);

    expect(await screen.findByText("Quedan 2 preguntas por responder.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Continuar postulación" })).toBeInTheDocument();
  });

  it("detenida ofrece reanudar", async () => {
    svc.getProposal.mockResolvedValue(
      vista({ status: "STOPPED", requirements: [requisito({ status: "no_cumple" })] }),
    );
    render(<ProposalEntryCard tenderId="t-1" isClosed={false} />);

    expect(await screen.findByRole("link", { name: "Reanudar" })).toBeInTheDocument();
  });

  it("lista ofrece ver el borrador", async () => {
    svc.getProposal.mockResolvedValue(vista({ status: "READY" }));
    render(<ProposalEntryCard tenderId="t-1" isClosed={false} />);

    expect(await screen.findByRole("link", { name: "Ver borrador" })).toBeInTheDocument();
  });

  it("sin permiso y sin postulación no ofrece generarla", async () => {
    permiso.puede = false;
    svc.getProposal.mockRejectedValue(new ApiError(404, "x"));
    render(<ProposalEntryCard tenderId="t-1" isClosed={false} />);

    expect(await screen.findByText(/Solo quienes pueden generar/)).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
