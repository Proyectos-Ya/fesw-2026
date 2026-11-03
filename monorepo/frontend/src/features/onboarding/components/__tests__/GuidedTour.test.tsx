import { act, render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Config } from "driver.js";
import { useOnboardingStore } from "../../store/useOnboardingStore";
import { GuidedTour } from "../GuidedTour";

const mockDrive = vi.fn();
const mockDestroy = vi.fn();
const mockIsActive = vi.fn(() => true);
const mockDriverFactory = vi.fn((_config?: Config) => ({
  drive: mockDrive,
  destroy: mockDestroy,
  isActive: mockIsActive,
  moveNext: vi.fn(),
  movePrevious: vi.fn(),
}));

vi.mock("driver.js", () => ({
  driver: (config?: Config) => mockDriverFactory(config),
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

  it("inicializa driver.js con los 3 pasos estratégicos y overlayColor difuminado cuando isTourActive es true", () => {
    useOnboardingStore.setState({ isTourActive: true, currentTourStep: 0 });

    render(<GuidedTour />);

    expect(mockDriverFactory).toHaveBeenCalledTimes(1);
    const config = mockDriverFactory.mock.calls[0]?.[0];
    expect(config).toBeDefined();
    expect(config?.showProgress).toBe(true);
    expect(config?.overlayColor).toBe("rgba(27, 24, 20, 0.65)");
    expect(config?.steps).toHaveLength(3);
    expect(config?.steps?.[0]?.element).toBe(
      '[data-tour="home-recommendations"]',
    );
    expect(config?.steps?.[1]?.element).toBe('[data-tour="sidebar-search"]');
    expect(config?.steps?.[2]?.element).toBe(
      '[data-tour="match-detail-panel"]',
    );
    expect(mockDrive).toHaveBeenCalledWith(0);
  });

  it("marca el onboarding como completado/omitido cuando driver.js se destruye", () => {
    useOnboardingStore.setState({ isTourActive: true, currentTourStep: 1 });

    render(<GuidedTour />);

    const config = mockDriverFactory.mock.calls[0]?.[0];
    expect(config?.onDestroyed).toBeTypeOf("function");

    // Simulamos que el usuario cierra/omite o finaliza el tour en driver.js
    act(() => {
      config?.onDestroyed?.(undefined, { popover: {} }, {
        config: config ?? {},
        state: {},
        driver: mockDriverFactory() as never,
        index: 1,
        reason: "close",
      });
    });

    const state = useOnboardingStore.getState();
    expect(state.isTourActive).toBe(false);
    expect(state.hasCompletedOnboarding).toBe(true);
  });
});
