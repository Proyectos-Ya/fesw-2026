import { renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { reportTenderInteraction } from "../../services/rankingTelemetryService";
import { useTenderInteractionReporter } from "../useTenderInteractionReporter";

vi.mock("../../services/rankingTelemetryService", () => ({
  reportTenderInteraction: vi.fn(),
}));

const RK = "0b6f3d2e-8f1a-4c53-9a6e-2d1c7b9e4a10";

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useTenderInteractionReporter", () => {
  it("informa cada tipo una sola vez por licitación y ranking", () => {
    const ranking = { rankingId: RK, position: 3 };
    const { result } = renderHook(() => useTenderInteractionReporter("t-1", ranking));

    result.current("asistente");
    result.current("asistente");
    result.current("analisis");

    expect(reportTenderInteraction).toHaveBeenCalledTimes(2);
    expect(reportTenderInteraction).toHaveBeenNthCalledWith(1, "t-1", "asistente", "detalle", {
      rankingId: RK,
      position: 3,
    });
    expect(reportTenderInteraction).toHaveBeenNthCalledWith(2, "t-1", "analisis", "detalle", {
      rankingId: RK,
      position: 3,
    });
  });

  it("sin ranking informa con null", () => {
    const { result } = renderHook(() => useTenderInteractionReporter("t-1", null));

    result.current("detalle");

    expect(reportTenderInteraction).toHaveBeenCalledWith("t-1", "detalle", "detalle", null);
  });
});
