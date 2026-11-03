import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useOnboardingStore } from "../../store/useOnboardingStore";
import { WelcomeModal } from "../WelcomeModal";

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

describe("WelcomeModal", () => {
  beforeEach(() => {
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

  it("no se renderiza si el store aún no se ha hidratado (_hasHydrated === false)", () => {
    useOnboardingStore.setState({ _hasHydrated: false });

    render(<WelcomeModal />);

    expect(
      screen.queryByRole("dialog", { name: /¡Bienvenido a Chiripa!/i }),
    ).not.toBeInTheDocument();
  });

  it("aplica el Soft Gate: no se renderiza si el usuario no tiene empresa ni workspace activo", () => {
    mockUseCompany.mockReturnValue({
      company: { status: "without-company" },
    });
    mockUseWorkspace.mockReturnValue({
      activeWorkspace: null,
    });

    render(<WelcomeModal />);

    expect(
      screen.queryByRole("dialog", { name: /¡Bienvenido a Chiripa!/i }),
    ).not.toBeInTheDocument();
  });

  it("no se renderiza si el usuario ya completó el onboarding o si el tour está activo", () => {
    useOnboardingStore.setState({ hasCompletedOnboarding: true });
    const { rerender } = render(<WelcomeModal />);
    expect(
      screen.queryByRole("dialog", { name: /¡Bienvenido a Chiripa!/i }),
    ).not.toBeInTheDocument();

    act(() => {
      useOnboardingStore.setState({
        hasCompletedOnboarding: false,
        isTourActive: true,
      });
    });
    rerender(<WelcomeModal />);
    expect(
      screen.queryByRole("dialog", { name: /¡Bienvenido a Chiripa!/i }),
    ).not.toBeInTheDocument();
  });

  it("se renderiza cuando el usuario es nuevo y tiene empresa activa", () => {
    render(<WelcomeModal />);

    expect(
      screen.getByRole("dialog", { name: /¡Bienvenido a Chiripa!/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Iniciar recorrido/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Omitir por ahora/i }),
    ).toBeInTheDocument();
  });

  it("dispara startTour al hacer clic en 'Iniciar recorrido'", () => {
    render(<WelcomeModal />);

    fireEvent.click(screen.getByRole("button", { name: /Iniciar recorrido/i }));

    const state = useOnboardingStore.getState();
    expect(state.isTourActive).toBe(true);
    expect(state.currentTourStep).toBe(0);
  });

  it("dispara skipTour al hacer clic en 'Omitir por ahora'", () => {
    render(<WelcomeModal />);

    fireEvent.click(screen.getByRole("button", { name: /Omitir por ahora/i }));

    const state = useOnboardingStore.getState();
    expect(state.hasCompletedOnboarding).toBe(true);
    expect(state.isTourActive).toBe(false);
  });
});
