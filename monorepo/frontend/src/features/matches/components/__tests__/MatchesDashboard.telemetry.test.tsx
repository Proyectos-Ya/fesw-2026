import React from "react";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MatchesDashboard } from "../MatchesDashboard";
import * as tenderService from "../../services/tenderService";
import * as savedService from "@/features/saved-tenders/services/savedTenders.service";
import { reportTenderInteraction } from "@/features/ranking-telemetry/services/rankingTelemetryService";
import { resetReportedImpressions } from "@/features/ranking-telemetry/hooks/useImpressionTracker";
import { installFakeIntersectionObserver } from "@/features/ranking-telemetry/test-utils";
import type { RecommendedMatch, Tender } from "../../tenderTypes";

const RK = "0b6f3d2e-8f1a-4c53-9a6e-2d1c7b9e4a10";

const mockRouter = { push: vi.fn(), replace: vi.fn() };
const mockUser = { id: "user-1", email: "test@example.com" };

vi.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
}));

vi.mock("@/features/auth/AuthContext", () => ({
  useAuth: () => ({ user: mockUser, isLoading: false, isAuthenticated: true }),
}));

vi.mock("../../services/tenderService", () => ({
  getRecommendedTenders: vi.fn(),
}));

vi.mock("@/features/saved-tenders/services/savedTenders.service", () => ({
  fetchSavedTenders: vi.fn(),
  saveTenderApi: vi.fn(),
  unsaveTenderApi: vi.fn(),
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

function tender(id: string, name: string, region: string): Tender {
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
    region,
    province: "Provincia",
    commune: "Comuna",
    available_amount_clp: 1000000,
    created_at: "2026-06-01T00:00:00Z",
    updated_at: "2026-06-01T00:00:00Z",
    items: [],
  };
}

function match(
  n: number,
  region: string,
  overrides: Partial<RecommendedMatch> = {},
): RecommendedMatch {
  return {
    id: `match-${n}`,
    supplier_id: "sup-1",
    tender_id: `tender-${n}`,
    similarity_score: 0.9,
    reranker_score: 0.9,
    final_score: 0.9,
    model_version: "v1",
    calculated_at: "2026-06-01T00:00:00Z",
    tender: tender(`tender-${n}`, `Licitación ${n}`, region),
    ranking_id: RK,
    ranking_position: n,
    ...overrides,
  };
}

let io: ReturnType<typeof installFakeIntersectionObserver>;

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers({ shouldAdvanceTime: true });
  io = installFakeIntersectionObserver();
  vi.mocked(savedService.fetchSavedTenders).mockResolvedValue([]);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  resetReportedImpressions();
});

describe("MatchesDashboard: telemetría del ranking", () => {
  it("registra la posición mostrada y no la servida", async () => {
    vi.mocked(tenderService.getRecommendedTenders).mockResolvedValue([
      match(1, "Metropolitana"),
      match(2, "Biobío"),
      match(3, "Biobío"),
    ]);
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<MatchesDashboard />);

    await screen.findByText("Licitación 2");
    await user.selectOptions(screen.getByLabelText("Región"), "Biobío");

    // Tras el filtro, la 2 pasa a ser la primera mostrada y la 3 la segunda.
    const link2 = screen.getByRole("link", { name: "Ver detalle de Licitación 2" });
    const link3 = screen.getByRole("link", { name: "Ver detalle de Licitación 3" });
    expect(link2).toHaveAttribute("href", `/matches/tender-2?r=${RK}&p=1`);
    expect(link3).toHaveAttribute("href", `/matches/tender-3?r=${RK}&p=2`);

    act(() => io.show(link2));
    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(reportTenderInteraction).toHaveBeenCalledWith("tender-2", "impresion", "matches", {
      rankingId: RK,
      position: 1,
    });
    expect(reportTenderInteraction).not.toHaveBeenCalledWith(
      expect.anything(),
      "impresion",
      expect.anything(),
      expect.objectContaining({ position: 2 }),
    );
  });

  it("sin ranking_id (backend anterior) el enlace no cambia y no se reporta nada", async () => {
    vi.mocked(tenderService.getRecommendedTenders).mockResolvedValue([
      match(1, "Metropolitana", { ranking_id: undefined, ranking_position: undefined }),
    ]);
    render(<MatchesDashboard />);

    const link = await screen.findByRole("link", { name: "Ver detalle de Licitación 1" });
    expect(link).toHaveAttribute("href", "/matches/tender-1");

    act(() => io.show(link));
    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(reportTenderInteraction).not.toHaveBeenCalled();
  });
});
