import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { reportTenderInteraction } from "../../services/rankingTelemetryService";
import { installFakeIntersectionObserver } from "../../test-utils";
import type { InteractionSource, RankingContext } from "../../types";
import {
  resetReportedImpressions,
  useImpressionRef,
  type ImpressionTarget,
} from "../useImpressionTracker";

vi.mock("../../services/rankingTelemetryService", () => ({
  reportTenderInteraction: vi.fn(),
}));

const RK = "0b6f3d2e-8f1a-4c53-9a6e-2d1c7b9e4a10";
const OTRO_RK = "7c2f1a90-3b64-4d1e-8a52-9e0d6c4b1f33";

function Tarjeta({ target }: { target: ImpressionTarget | null }) {
  const ref = useImpressionRef(target);
  return <div ref={ref} data-testid="tarjeta" />;
}

function objetivo(rankingId = RK, source: InteractionSource = "matches"): ImpressionTarget {
  const ranking: RankingContext = { rankingId, position: 1 };
  return { tenderId: "t-1", ranking, source };
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.clearAllMocks();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  resetReportedImpressions();
});

describe("useImpressionRef", () => {
  it("cuenta una sola vez por tarjeta y ranking, aunque se oculte, se muestre o se remonte", () => {
    const io = installFakeIntersectionObserver();
    const { unmount } = render(<Tarjeta target={objetivo()} />);
    let el = screen.getByTestId("tarjeta");

    act(() => io.show(el));
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    act(() => io.hide(el));
    act(() => io.show(el));
    act(() => {
      vi.advanceTimersByTime(1000);
    });

    unmount();
    render(<Tarjeta target={objetivo()} />);
    el = screen.getByTestId("tarjeta");
    act(() => io.show(el));
    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(reportTenderInteraction).toHaveBeenCalledTimes(1);
    expect(reportTenderInteraction).toHaveBeenCalledWith("t-1", "impresion", "matches", {
      rankingId: RK,
      position: 1,
    });
  });

  it("no cuenta si se oculta antes de 1 s", () => {
    const io = installFakeIntersectionObserver();
    render(<Tarjeta target={objetivo()} />);
    const el = screen.getByTestId("tarjeta");

    act(() => io.show(el));
    act(() => {
      vi.advanceTimersByTime(500);
    });
    act(() => io.hide(el));
    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(reportTenderInteraction).not.toHaveBeenCalled();
  });

  it("no cuenta con menos de la mitad a la vista", () => {
    const io = installFakeIntersectionObserver();
    render(<Tarjeta target={objetivo()} />);
    const el = screen.getByTestId("tarjeta");

    act(() => io.show(el, 0.3));
    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(reportTenderInteraction).not.toHaveBeenCalled();
  });

  it("otro ranking para la misma licitación sí cuenta", () => {
    const io = installFakeIntersectionObserver();
    const { rerender } = render(<Tarjeta target={objetivo(RK)} />);
    act(() => io.show(screen.getByTestId("tarjeta")));
    act(() => {
      vi.advanceTimersByTime(1000);
    });

    rerender(<Tarjeta target={objetivo(OTRO_RK)} />);
    act(() => io.show(screen.getByTestId("tarjeta")));
    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(reportTenderInteraction).toHaveBeenCalledTimes(2);
  });

  it("sin IntersectionObserver renderiza sin errores y no reporta", () => {
    expect(() => render(<Tarjeta target={objetivo()} />)).not.toThrow();
    act(() => {
      vi.advanceTimersByTime(5000);
    });

    expect(reportTenderInteraction).not.toHaveBeenCalled();
  });

  it("con target null no crea observadores", () => {
    const constructor = vi.fn();
    vi.stubGlobal(
      "IntersectionObserver",
      class {
        constructor() {
          constructor();
        }
        observe() {}
        unobserve() {}
        disconnect() {}
        takeRecords() {
          return [];
        }
      },
    );

    render(<Tarjeta target={null} />);

    expect(constructor).not.toHaveBeenCalled();
  });
});
