import { act, render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Config, Driver, DriveStep } from "driver.js";
import { useOnboardingStore } from "../../store/useOnboardingStore";
import {
  GuidedTour,
  HOME_STEPS,
  DETAIL_STEPS,
  DRAFT_STEPS,
} from "../GuidedTour";

let isDriverActive = false;
const mockDrive = vi.fn(() => {
  isDriverActive = true;
});
const mockDestroy = vi.fn(() => {
  isDriverActive = false;
});
const mockMoveTo = vi.fn();
const mockIsActive = vi.fn(() => isDriverActive);
const mockDriverInstance = {
  drive: mockDrive,
  destroy: mockDestroy,
  isActive: mockIsActive,
  moveNext: vi.fn(),
  movePrevious: vi.fn(),
  moveTo: mockMoveTo,
} as unknown as Driver;

const mockDriverFactory = vi.fn((_config?: Config) => mockDriverInstance);

vi.mock("driver.js", () => ({
  driver: (config?: Config) => mockDriverFactory(config),
}));

vi.mock("../../services/onboardingService", () => ({
  markOnboardingCompletedApi: vi.fn().mockResolvedValue({}),
}));

describe("GuidedTour", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    isDriverActive = false;
    useOnboardingStore.setState({
      tours: {
        home: false,
        detail: false,
        draft: false,
      },
      activeTour: null,
      currentTourStep: 0,
      isHelpCenterOpen: false,
      _hasHydrated: true,
    });
  });

  it("no inicializa driver.js cuando activeTour es null", () => {
    const { container } = render(<GuidedTour />);

    expect(container.firstChild).toBeNull();
    expect(mockDriverFactory).not.toHaveBeenCalled();
    expect(mockDrive).not.toHaveBeenCalled();
  });

  it("inicializa driver.js con HOME_STEPS y configuración de modo oscuro cuando activeTour === 'home'", () => {
    useOnboardingStore.setState({ activeTour: "home", currentTourStep: 0 });

    render(<GuidedTour />);

    expect(mockDriverFactory).toHaveBeenCalledTimes(1);
    const config = mockDriverFactory.mock.calls[0]?.[0];
    expect(config).toBeDefined();
    expect(config?.showProgress).toBe(true);
    expect(config?.overlayColor).toBe("rgba(27, 24, 20, 0.65)");
    expect(config?.popoverClass).toContain("chiripa-tour-popover");
    expect(config?.popoverClass).toContain("dark:bg-gray-900");

    const steps = config?.steps as DriveStep[];
    expect(steps).toHaveLength(HOME_STEPS.length);
    expect(steps[0]?.element).toBe('[data-tour="home-recommendations"]');
    expect(steps[1]?.element).toBe('[data-tour="sidebar-search"]');
    expect(steps[2]?.element).toBe('[data-tour="sidebar-help"]');

    expect(mockDrive).toHaveBeenCalledWith(0);
  });

  it("inicializa driver.js con DETAIL_STEPS cuando activeTour === 'detail'", () => {
    useOnboardingStore.setState({ activeTour: "detail", currentTourStep: 0 });

    render(<GuidedTour />);

    expect(mockDriverFactory).toHaveBeenCalledTimes(1);
    const config = mockDriverFactory.mock.calls[0]?.[0];
    const steps = config?.steps as DriveStep[];
    expect(steps).toHaveLength(DETAIL_STEPS.length);
    expect(steps[0]?.element).toBe('[data-tour="match-detail-panel"]');
    expect(mockDrive).toHaveBeenCalledWith(0);
  });

  it("inicializa driver.js con DRAFT_STEPS cuando activeTour === 'draft'", () => {
    useOnboardingStore.setState({ activeTour: "draft", currentTourStep: 0 });

    render(<GuidedTour />);

    expect(mockDriverFactory).toHaveBeenCalledTimes(1);
    const config = mockDriverFactory.mock.calls[0]?.[0];
    const steps = config?.steps as DriveStep[];
    expect(steps).toHaveLength(DRAFT_STEPS.length);
    expect(steps[0]?.element).toBe('[data-tour="proposal-editor"]');
    expect(mockDrive).toHaveBeenCalledWith(0);
  });

  it("en onNextClick avanza dentro del mismo tour o lo finaliza al alcanzar el último paso", () => {
    useOnboardingStore.setState({ activeTour: "home", currentTourStep: 0 });

    render(<GuidedTour />);

    const config = mockDriverFactory.mock.calls[0]?.[0];
    expect(config?.onNextClick).toBeTypeOf("function");

    // Paso 0 -> Paso 1
    act(() => {
      config?.onNextClick?.(undefined, HOME_STEPS[0], {
        config: config ?? {},
        state: { activeIndex: 0 },
        driver: mockDriverInstance,
        index: 0,
      });
    });

    expect(mockMoveTo).toHaveBeenCalledWith(1);
    expect(useOnboardingStore.getState().currentTourStep).toBe(1);

    // Último paso -> Finalizar
    act(() => {
      config?.onNextClick?.(undefined, HOME_STEPS[2], {
        config: config ?? {},
        state: { activeIndex: 2 },
        driver: mockDriverInstance,
        index: 2,
      });
    });

    expect(mockDestroy).toHaveBeenCalledTimes(1);
    const state = useOnboardingStore.getState();
    expect(state.activeTour).toBeNull();
    expect(state.tours.home).toBe(true);
  });

  it("en onPrevClick retrocede al paso anterior", () => {
    useOnboardingStore.setState({ activeTour: "home", currentTourStep: 2 });

    render(<GuidedTour />);

    const config = mockDriverFactory.mock.calls[0]?.[0];
    expect(config?.onPrevClick).toBeTypeOf("function");

    act(() => {
      config?.onPrevClick?.(undefined, HOME_STEPS[2], {
        config: config ?? {},
        state: { activeIndex: 2 },
        driver: mockDriverInstance,
        index: 2,
      });
    });

    expect(mockMoveTo).toHaveBeenCalledWith(1);
    expect(useOnboardingStore.getState().currentTourStep).toBe(1);
  });

  it("marca el tour activo como completado al cerrarse o destruirse", () => {
    useOnboardingStore.setState({ activeTour: "detail", currentTourStep: 0 });

    render(<GuidedTour />);

    const config = mockDriverFactory.mock.calls[0]?.[0];
    expect(config?.onCloseClick).toBeTypeOf("function");

    act(() => {
      config?.onCloseClick?.(undefined, DETAIL_STEPS[0], {
        config: config ?? {},
        state: {},
        driver: mockDriverInstance,
        index: 0,
      });
    });

    const state = useOnboardingStore.getState();
    expect(state.activeTour).toBeNull();
    expect(state.tours.detail).toBe(true);
  });
});
