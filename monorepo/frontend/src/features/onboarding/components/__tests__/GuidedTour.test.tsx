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

  it("inicializa driver.js con allowClose en false, HOME_STEPS y configuración de modo oscuro cuando activeTour === 'home'", () => {
    useOnboardingStore.setState({ activeTour: "home", currentTourStep: 0 });

    render(<GuidedTour />);

    expect(mockDriverFactory).toHaveBeenCalledTimes(1);
    const config = mockDriverFactory.mock.calls[0]?.[0];
    expect(config).toBeDefined();
    expect(config?.showProgress).toBe(true);
    expect(config?.allowClose).toBe(false);
    expect(config?.overlayColor).toBe("rgba(27, 24, 20, 0.65)");
    expect(config?.popoverClass).toContain("chiripa-tour-popover");
    expect(config?.popoverClass).toContain("dark:bg-gray-900");

    const steps = config?.steps as DriveStep[];
    expect(steps).toHaveLength(6);
    expect(steps[0]?.element).toBe('[data-tour="home-recommendations"]');
    expect(steps[1]?.element).toBe('[data-tour="sidebar-search"]');
    expect(steps[2]?.element).toBe('[data-tour="sidebar-matches"]');
    expect(steps[3]?.element).toBe('[data-tour="sidebar-seguimiento"]');
    expect(steps[4]?.element).toBe('[data-tour="sidebar-administracion"]');
    expect(steps[5]?.element).toBe('[data-tour="help-center-trigger"]');

    expect(mockDrive).toHaveBeenCalledWith(0);
  });

  it("inicializa driver.js con DETAIL_STEPS cuando activeTour === 'detail'", () => {
    useOnboardingStore.setState({ activeTour: "detail", currentTourStep: 0 });

    render(<GuidedTour />);

    expect(mockDriverFactory).toHaveBeenCalledTimes(1);
    const config = mockDriverFactory.mock.calls[0]?.[0];
    const steps = config?.steps as DriveStep[];
    expect(steps).toHaveLength(6);
    expect(steps[0]?.element).toBe('[data-tour="detail-header"]');
    expect(steps[1]?.element).toBe('[data-tour="detail-actions"]');
    expect(steps[2]?.element).toBe('[data-tour="detail-ai-panel"]');
    expect(steps[3]?.element).toBe('[data-tour="detail-bases"]');
    expect(steps[4]?.element).toBe('[data-tour="detail-anexos"]');
    expect(steps[5]?.element).toBe('[data-tour="detail-calendario"]');
    expect(mockDrive).toHaveBeenCalledWith(0);
  });

  it("en activeTour === 'detail', onHighlightStarted activa la pestaña correspondiente para los pasos 4, 5 y 6", () => {
    useOnboardingStore.setState({ activeTour: "detail", currentTourStep: 0 });

    const basesBtn = document.createElement("button");
    basesBtn.setAttribute("data-tab-target", "bases");
    const anexosBtn = document.createElement("button");
    anexosBtn.setAttribute("data-tab-target", "anexos");
    const calendarioBtn = document.createElement("button");
    calendarioBtn.setAttribute("data-tab-target", "calendario");

    const basesClickSpy = vi.spyOn(basesBtn, "click");
    const anexosClickSpy = vi.spyOn(anexosBtn, "click");
    const calendarioClickSpy = vi.spyOn(calendarioBtn, "click");

    document.body.appendChild(basesBtn);
    document.body.appendChild(anexosBtn);
    document.body.appendChild(calendarioBtn);

    try {
      render(<GuidedTour />);

      const config = mockDriverFactory.mock.calls[0]?.[0];
      expect(config?.onHighlightStarted).toBeTypeOf("function");

      // Paso 4 (índice 3) -> Bases
      act(() => {
        config?.onHighlightStarted?.(undefined, DETAIL_STEPS[3], {
          config: config ?? {},
          state: { activeIndex: 3 },
          driver: mockDriverInstance,
          index: 3,
        });
      });
      expect(basesClickSpy).toHaveBeenCalledTimes(1);
      expect(useOnboardingStore.getState().currentTourStep).toBe(3);

      // Paso 5 (índice 4) -> Anexos
      act(() => {
        config?.onHighlightStarted?.(undefined, DETAIL_STEPS[4], {
          config: config ?? {},
          state: { activeIndex: 4 },
          driver: mockDriverInstance,
          index: 4,
        });
      });
      expect(anexosClickSpy).toHaveBeenCalledTimes(1);
      expect(useOnboardingStore.getState().currentTourStep).toBe(4);

      // Paso 6 (índice 5) -> Calendario
      act(() => {
        config?.onHighlightStarted?.(undefined, DETAIL_STEPS[5], {
          config: config ?? {},
          state: { activeIndex: 5 },
          driver: mockDriverInstance,
          index: 5,
        });
      });
      expect(calendarioClickSpy).toHaveBeenCalledTimes(1);
      expect(useOnboardingStore.getState().currentTourStep).toBe(5);
    } finally {
      document.body.removeChild(basesBtn);
      document.body.removeChild(anexosBtn);
      document.body.removeChild(calendarioBtn);
    }
  });

  it("inicializa driver.js con DRAFT_STEPS cuando activeTour === 'draft'", () => {
    useOnboardingStore.setState({ activeTour: "draft", currentTourStep: 0 });

    render(<GuidedTour />);

    expect(mockDriverFactory).toHaveBeenCalledTimes(1);
    const config = mockDriverFactory.mock.calls[0]?.[0];
    const steps = config?.steps as DriveStep[];
    expect(steps).toHaveLength(3);
    expect(steps[0]?.element).toBe('[data-tour="draft-factibilidad"]');
    expect(steps[1]?.element).toBe('[data-tour="draft-borrador-container"]');
    expect(steps[2]?.element).toBe('[data-tour="draft-cotizacion"]');
    expect(mockDrive).toHaveBeenCalledWith(0);
  });

  it("en activeTour === 'draft', onHighlightStarted activa la pestaña y abre la cotización para los pasos correspondientes", () => {
    vi.useFakeTimers();
    useOnboardingStore.setState({ activeTour: "draft", currentTourStep: 0 });

    const factibilidadBtn = document.createElement("button");
    factibilidadBtn.setAttribute("data-tab-target", "factibilidad");
    const borradorBtn = document.createElement("button");
    borradorBtn.setAttribute("data-tab-target", "borrador");
    const cotizacionBtn = document.createElement("button");
    cotizacionBtn.setAttribute("data-tab-target", "cotizacion");
    const toggleQuotationBtn = document.createElement("button");
    toggleQuotationBtn.setAttribute("data-action", "toggle-quotation");
    toggleQuotationBtn.setAttribute("aria-expanded", "false");

    const factibilidadClickSpy = vi.spyOn(factibilidadBtn, "click");
    const borradorClickSpy = vi.spyOn(borradorBtn, "click");
    const cotizacionClickSpy = vi.spyOn(cotizacionBtn, "click");
    const toggleQuotationClickSpy = vi.spyOn(toggleQuotationBtn, "click");

    document.body.appendChild(factibilidadBtn);
    document.body.appendChild(borradorBtn);
    document.body.appendChild(cotizacionBtn);
    document.body.appendChild(toggleQuotationBtn);

    try {
      render(<GuidedTour />);

      const config = mockDriverFactory.mock.calls[0]?.[0];

      // Paso 1 (índice 0) -> Factibilidad
      act(() => {
        config?.onHighlightStarted?.(undefined, DRAFT_STEPS[0], {
          config: config ?? {},
          state: { activeIndex: 0 },
          driver: mockDriverInstance,
          index: 0,
        });
      });
      expect(factibilidadClickSpy).toHaveBeenCalledTimes(1);
      expect(useOnboardingStore.getState().currentTourStep).toBe(0);

      // Paso 2 (índice 1) -> Borrador
      act(() => {
        config?.onHighlightStarted?.(undefined, DRAFT_STEPS[1], {
          config: config ?? {},
          state: { activeIndex: 1 },
          driver: mockDriverInstance,
          index: 1,
        });
      });
      expect(borradorClickSpy).toHaveBeenCalledTimes(1);
      expect(useOnboardingStore.getState().currentTourStep).toBe(1);

      // Paso 3 (índice 2) -> Cotización
      act(() => {
        config?.onHighlightStarted?.(undefined, DRAFT_STEPS[2], {
          config: config ?? {},
          state: { activeIndex: 2 },
          driver: mockDriverInstance,
          index: 2,
        });
      });
      expect(cotizacionClickSpy).toHaveBeenCalledTimes(1);
      expect(useOnboardingStore.getState().currentTourStep).toBe(2);

      // Avanzar temporizador para el clic automático de abrir cotización
      act(() => {
        vi.advanceTimersByTime(100);
      });
      expect(toggleQuotationClickSpy).toHaveBeenCalledTimes(1);
    } finally {
      document.body.removeChild(factibilidadBtn);
      document.body.removeChild(borradorBtn);
      document.body.removeChild(cotizacionBtn);
      document.body.removeChild(toggleQuotationBtn);
      vi.useRealTimers();
    }
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
    const lastStepIndex = HOME_STEPS.length - 1;
    act(() => {
      config?.onNextClick?.(undefined, HOME_STEPS[lastStepIndex], {
        config: config ?? {},
        state: { activeIndex: lastStepIndex },
        driver: mockDriverInstance,
        index: lastStepIndex,
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
