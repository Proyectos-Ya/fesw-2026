import React from "react";
import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { HomeDashboard } from "../HomeDashboard";
import * as tenderService from "../../services/tenderService";
import { reportTenderInteraction } from "@/features/ranking-telemetry/services/rankingTelemetryService";
import { resetReportedImpressions } from "@/features/ranking-telemetry/hooks/useImpressionTracker";
import { installFakeIntersectionObserver } from "@/features/ranking-telemetry/test-utils";
import type { RecommendedMatch, Tender } from "../../tenderTypes";

const RK = "0b6f3d2e-8f1a-4c53-9a6e-2d1c7b9e4a10";

const STABLE_ROUTER = { replace: vi.fn(), push: vi.fn() };
const STABLE_USER = { id: "u-1", email: "usuario@empresa.cl", full_name: "Usuario" };
const EMPTY_QUESTIONS: never[] = [];

vi.mock("next/navigation", () => ({
  useRouter: () => STABLE_ROUTER,
}));

vi.mock("@/features/auth/AuthContext", () => ({
  useAuth: () => ({ user: STABLE_USER, isLoading: false, isAuthenticated: true }),
}));

vi.mock("../../services/tenderService", () => ({
  getRecommendedTenders: vi.fn(),
}));

vi.mock("../../hooks/useSmartQuestions", () => ({
  useSmartQuestions: () => ({ questions: EMPTY_QUESTIONS }),
}));

vi.mock("../../services/questionService", () => ({
  answerSmartQuestion: vi.fn(),
}));

vi.mock("@/features/ranking-telemetry/services/rankingTelemetryService", () => ({
  reportTenderInteraction: vi.fn(),
}));

// Un <a> que no navega: en jsdom no hay router.
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: React.ComponentProps<"a"> & { href: string }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

function tender(id: string, name: string): Tender {
  return {
    id,
    code: `${id}-COT26`,
    name,
    description: "Descripción",
    status_id: 2,
    status_code: "publicada",
    published_at: "2026-06-01T00:00:00Z",
    closing_at: "2099-06-25T00:00:00Z",
    last_change_at: "2026-06-01T00:00:00Z",
    buyer_rut: "111-1",
    buyer_name: "Subsecretaría",
    buyer_unit: "Informática",
    region: "Metropolitana",
    province: "Santiago",
    commune: "Santiago",
    available_amount_clp: 1000000,
    created_at: "2026-06-01T00:00:00Z",
    updated_at: "2026-06-01T00:00:00Z",
    items: [],
  };
}

function match(n: number, finalScore: number): RecommendedMatch {
  return {
    id: `m${n}`,
    supplier_id: "sup-1",
    tender_id: `t${n}`,
    similarity_score: finalScore,
    reranker_score: finalScore,
    final_score: finalScore,
    model_version: "v1",
    calculated_at: "2026-06-01T00:00:00Z",
    tender: tender(`t${n}`, `Licitación ${n}`),
    ranking_id: RK,
    ranking_position: n,
  };
}

let io: ReturnType<typeof installFakeIntersectionObserver>;

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers({ shouldAdvanceTime: true });
  io = installFakeIntersectionObserver();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  resetReportedImpressions();
});

describe("HomeDashboard: telemetría del ranking", () => {
  it("la posición es la de la lista filtrada por verde, no la servida", async () => {
    vi.mocked(tenderService.getRecommendedTenders).mockResolvedValue([
      match(1, 0.5), // no es verde: no se muestra
      match(2, 0.9),
      match(3, 0.8),
    ]);
    render(<HomeDashboard />);

    const link2 = await screen.findByRole("link", { name: "Ver detalle de Licitación 2" });
    const link3 = screen.getByRole("link", { name: "Ver detalle de Licitación 3" });
    expect(screen.queryByRole("link", { name: "Ver detalle de Licitación 1" })).toBeNull();
    expect(link2).toHaveAttribute("href", `/matches/t2?r=${RK}&p=1`);
    expect(link3).toHaveAttribute("href", `/matches/t3?r=${RK}&p=2`);

    act(() => io.show(link2));
    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(reportTenderInteraction).toHaveBeenCalledTimes(1);
    expect(reportTenderInteraction).toHaveBeenCalledWith("t2", "impresion", "inicio", {
      rankingId: RK,
      position: 1,
    });
  });
});
