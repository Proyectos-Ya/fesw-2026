import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiDownload, apiFetch } from "@/features/shared/api/client";
import {
  answerProposalQuestion,
  decideDiscrepancy,
  downloadTechnicalDocument,
  generateProposal,
  getProposal,
  reanalyzeProposal,
  regenerateProposal,
  resumeProposal,
  startFeasibility,
} from "../proposalService";

vi.mock("@/features/shared/api/client", () => ({
  apiFetch: vi.fn(),
  apiDownload: vi.fn(),
}));

const fetchMock = vi.mocked(apiFetch);

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockResolvedValue({});
});

function llamada(): [string, RequestInit | undefined] {
  return fetchMock.mock.calls[0] as [string, RequestInit | undefined];
}

describe("proposalService", () => {
  it("lee el borrador de la empresa activa", async () => {
    await getProposal("t-1");
    expect(fetchMock).toHaveBeenCalledWith("/tenders/t-1/proposal");
  });

  it("inicia la factibilidad", async () => {
    await startFeasibility("t-1");
    expect(llamada()).toEqual(["/tenders/t-1/proposal/feasibility", { method: "POST" }]);
  });

  it("vuelve a analizar", async () => {
    await reanalyzeProposal("t-1");
    expect(llamada()).toEqual(["/tenders/t-1/proposal/reanalyze", { method: "POST" }]);
  });

  it("responde una pregunta de la postulación", async () => {
    await answerProposalQuestion("t-1", "q-1", "Sí");
    const [url, init] = llamada();
    expect(url).toBe("/tenders/t-1/proposal/questions/q-1/answer");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body))).toEqual({ answer: "Sí" });
  });

  it("decide sobre la exigencia que el usuario vio", async () => {
    await decideDiscrepancy("t-1", "req-2", "stop");
    const [url, init] = llamada();
    expect(url).toBe("/tenders/t-1/proposal/discrepancy");
    expect(JSON.parse(String(init?.body))).toEqual({
      requirement_id: "req-2",
      action: "stop",
    });
  });

  it("reanuda, redacta y regenera", async () => {
    await resumeProposal("t-1");
    await generateProposal("t-1");
    await regenerateProposal("t-1", "Más formal");

    const urls = fetchMock.mock.calls.map((c) => c[0]);
    expect(urls).toEqual([
      "/tenders/t-1/proposal/resume",
      "/tenders/t-1/proposal/generate",
      "/tenders/t-1/proposal/regenerate",
    ]);
    const init = fetchMock.mock.calls[2][1] as RequestInit;
    expect(JSON.parse(String(init.body))).toEqual({ instructions: "Más formal" });
  });

  it("descarga el documento técnico", async () => {
    vi.mocked(apiDownload).mockResolvedValue({ blob: new Blob(), filename: "x.docx" });

    await downloadTechnicalDocument("t-1");

    expect(apiDownload).toHaveBeenCalledWith(
      "/tenders/t-1/proposal/export.docx",
      "documento-tecnico.docx",
    );
  });
});
