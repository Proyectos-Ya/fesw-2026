import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useProcessingPoll } from "../useProcessingPoll";

describe("useProcessingPoll", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("llama onTick periódicamente cuando está activo", () => {
    const onTick = vi.fn();
    renderHook(() => useProcessingPoll(true, onTick, { intervalMs: 15_000 }));

    expect(onTick).not.toHaveBeenCalled();

    vi.advanceTimersByTime(15_000);
    expect(onTick).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(30_000);
    expect(onTick).toHaveBeenCalledTimes(3);
  });

  it("se detiene cuando pasa a inactivo", () => {
    const onTick = vi.fn();
    const { rerender } = renderHook(
      ({ active }) => useProcessingPoll(active, onTick, { intervalMs: 15_000 }),
      { initialProps: { active: true } }
    );

    vi.advanceTimersByTime(15_000);
    expect(onTick).toHaveBeenCalledTimes(1);

    rerender({ active: false });
    vi.advanceTimersByTime(30_000);
    expect(onTick).toHaveBeenCalledTimes(1);
  });

  it("respeta maxTicks", () => {
    const onTick = vi.fn();
    renderHook(() =>
      useProcessingPoll(true, onTick, { intervalMs: 15_000, maxTicks: 2 })
    );

    vi.advanceTimersByTime(15_000);
    expect(onTick).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(15_000);
    expect(onTick).toHaveBeenCalledTimes(2);

    vi.advanceTimersByTime(30_000);
    expect(onTick).toHaveBeenCalledTimes(2);
  });

  it("no ejecuta ticks si está inactivo desde el inicio", () => {
    const onTick = vi.fn();
    renderHook(() => useProcessingPoll(false, onTick, { intervalMs: 15_000 }));

    vi.advanceTimersByTime(60_000);
    expect(onTick).not.toHaveBeenCalled();
  });
});
