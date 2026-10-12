import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ProposalStage } from "../../types";
import { useStageMessage } from "../useStageMessage";

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useStageMessage", () => {
  it("sin etapa no hay mensaje", () => {
    const { result } = renderHook(() => useStageMessage(null));
    expect(result.current).toBeNull();
  });

  it("cambia el texto a los 10 s y a los 30 s", () => {
    const { result } = renderHook(() => useStageMessage("analyzing"));
    const inicial = result.current;
    expect(inicial).toBe("Analizando bases y experiencia…");

    act(() => vi.advanceTimersByTime(9_999));
    expect(result.current).toBe(inicial);

    act(() => vi.advanceTimersByTime(1));
    const segundo = result.current;
    expect(segundo).not.toBe(inicial);

    act(() => vi.advanceTimersByTime(20_000));
    expect(result.current).not.toBe(segundo);
    expect(result.current).toMatch(/dos minutos/);
  });

  it("al cambiar de etapa vuelve al primer mensaje", () => {
    const { result, rerender } = renderHook(
      ({ stage }: { stage: ProposalStage }) => useStageMessage(stage),
      { initialProps: { stage: "drafting" as ProposalStage } },
    );
    act(() => vi.advanceTimersByTime(30_000));

    rerender({ stage: "regenerating" });

    expect(result.current).toBe("Regenerando el borrador con tus instrucciones…");
  });
});
