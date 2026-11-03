import { act, render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Config, Driver } from "driver.js";
import { useOnboardingStore } from "../../store/useOnboardingStore";
import { GuidedTour, GUIDED_TOUR_STEPS, type TourStep } from "../GuidedTour";

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

const mockPush = vi.fn();
let currentMockPathname = "/";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
  usePathname: () => currentMockPathname,
}));

const mockUseCompany = vi.fn();
const mockUseWorkspace = vi.fn();

vi.mock("../../services/onboardingService", () => ({
  markOnboardingCompletedApi: vi.fn().mockResolvedValue({}),
}));

vi.mock("@/features/company-profile/components/CompanyProvider", () => ({
  useCompany: () => mockUseCompany(),
}));

vi.mock("@/features/workspaces/WorkspaceContext", () => ({
  useWorkspace: () => mockUseWorkspace(),
}));

describe("GuidedTour", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    currentMockPathname = "/";
    isDriverActive = false;
    useOnboardingStore.setState({
      hasCompletedOnboarding: false,
      isTourActive: false,
      currentTourStep: 0,
      isHelpCenterOpen: false,
      _hasHydrated: true,
    });
    mockUseCompany.mockReturnValue({
      company: {
        status: "with-company",
        supplier: { id: "sup-1", name: "Empresa Demo" },
      },
    });
    mockUseWorkspace.mockReturnValue({
      activeWorkspace: null,
    });
  });

  it("no inicializa driver.js cuando isTourActive es false", () => {
    const { container } = render(<GuidedTour />);

    expect(container.firstChild).toBeNull();
    expect(mockDriverFactory).not.toHaveBeenCalled();
    expect(mockDrive).not.toHaveBeenCalled();
  });

  it("aplica el Soft Gate: no inicia driver.js si el usuario no tiene empresa ni workspace activo", () => {
    mockUseCompany.mockReturnValue({
      company: { status: "without-company" },
    });
    useOnboardingStore.setState({ isTourActive: true });

    render(<GuidedTour />);

    expect(mockDrive).not.toHaveBeenCalled();
  });

  it("inicializa driver.js con rutas multi-página, estilos para modo oscuro y overlayColor difuminado", () => {
    useOnboardingStore.setState({ isTourActive: true, currentTourStep: 0 });

    render(<GuidedTour />);

    expect(mockDriverFactory).toHaveBeenCalledTimes(1);
    const config = mockDriverFactory.mock.calls[0]?.[0];
    expect(config).toBeDefined();
    expect(config?.showProgress).toBe(true);
    expect(config?.overlayColor).toBe("rgba(27, 24, 20, 0.65)");
    expect(config?.popoverClass).toContain("chiripa-tour-popover");
    expect(config?.popoverClass).toContain("dark:bg-gray-900");

    const steps = config?.steps as TourStep[];
    expect(steps).toHaveLength(3);
    expect(steps[0]?.element).toBe('[data-tour="home-recommendations"]');
    expect(steps[0]?.route).toBe("/");
    expect(steps[1]?.element).toBe('[data-tour="sidebar-search"]');
    expect(steps[1]?.route).toBe("/buscar");
    expect(steps[2]?.element).toBe('[data-tour="match-detail-panel"]');
    expect(steps[2]?.route).toBe("/buscar");

    expect(mockDrive).toHaveBeenCalledWith(0);
  });

  it("en onNextClick navega a la siguiente ruta cuando difiere del pathname actual sin completar el onboarding", () => {
    currentMockPathname = "/";
    useOnboardingStore.setState({ isTourActive: true, currentTourStep: 0 });

    render(<GuidedTour />);

    const config = mockDriverFactory.mock.calls[0]?.[0];
    expect(config?.onNextClick).toBeTypeOf("function");

    // Simulamos clic en 'Siguiente' en el paso 0 (Home -> Buscar)
    act(() => {
      config?.onNextClick?.(undefined, GUIDED_TOUR_STEPS[0], {
        config: config ?? {},
        state: { activeIndex: 0 },
        driver: mockDriverInstance,
        index: 0,
      });
    });

    expect(mockDestroy).toHaveBeenCalledTimes(1);
    expect(mockPush).toHaveBeenCalledWith("/buscar");
    expect(useOnboardingStore.getState().currentTourStep).toBe(1);
    // No debe haberse marcado como completado porque es una transición interna
    expect(useOnboardingStore.getState().hasCompletedOnboarding).toBe(false);
  });

  it("en onPrevClick navega a la ruta anterior cuando difiere del pathname actual", () => {
    currentMockPathname = "/buscar";
    useOnboardingStore.setState({ isTourActive: true, currentTourStep: 1 });

    render(<GuidedTour />);

    const config = mockDriverFactory.mock.calls[0]?.[0];
    expect(config?.onPrevClick).toBeTypeOf("function");

    // Simulamos clic en 'Anterior' en el paso 1 (/buscar -> /)
    act(() => {
      config?.onPrevClick?.(undefined, GUIDED_TOUR_STEPS[1], {
        config: config ?? {},
        state: { activeIndex: 1 },
        driver: mockDriverInstance,
        index: 1,
      });
    });

    expect(mockDestroy).toHaveBeenCalledTimes(1);
    expect(mockPush).toHaveBeenCalledWith("/");
    expect(useOnboardingStore.getState().currentTourStep).toBe(0);
  });

  it("en onNextClick finaliza el tour si se encuentra en el último paso", () => {
    currentMockPathname = "/buscar";
    useOnboardingStore.setState({ isTourActive: true, currentTourStep: 2 });

    render(<GuidedTour />);

    const config = mockDriverFactory.mock.calls[0]?.[0];

    act(() => {
      config?.onNextClick?.(undefined, GUIDED_TOUR_STEPS[2], {
        config: config ?? {},
        state: { activeIndex: 2 },
        driver: mockDriverInstance,
        index: 2,
      });
    });

    expect(mockDestroy).toHaveBeenCalledTimes(1);
    const state = useOnboardingStore.getState();
    expect(state.isTourActive).toBe(false);
    expect(state.hasCompletedOnboarding).toBe(true);
  });

  it("marca el onboarding como completado/omitido cuando driver.js se destruye por acción del usuario", () => {
    currentMockPathname = "/buscar";
    useOnboardingStore.setState({ isTourActive: true, currentTourStep: 1 });

    render(<GuidedTour />);

    const config = mockDriverFactory.mock.calls[0]?.[0];
    expect(config?.onDestroyed).toBeTypeOf("function");

    act(() => {
      config?.onDestroyed?.(undefined, { popover: {} }, {
        config: config ?? {},
        state: {},
        driver: mockDriverInstance,
        index: 1,
        reason: "close",
      });
    });

    const state = useOnboardingStore.getState();
    expect(state.isTourActive).toBe(false);
    expect(state.hasCompletedOnboarding).toBe(true);
  });
});
