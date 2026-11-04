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

  it("no se renderiza si el usuario ya completó el tour de inicio o si hay un tour activo", () => {
    useOnboardingStore.setState({
      tours: { home: true, detail: false, draft: false },
    });
    const { rerender } = render(<WelcomeModal />);
    expect(
      screen.queryByRole("dialog", { name: /¡Bienvenido a Chiripa!/i }),
    ).not.toBeInTheDocument();

    act(() => {
      useOnboardingStore.setState({
        tours: { home: false, detail: false, draft: false },
        activeTour: "home",
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

  it("dispara startTour('home') al hacer clic en 'Iniciar recorrido'", () => {
    render(<WelcomeModal />);

    fireEvent.click(screen.getByRole("button", { name: /Iniciar recorrido/i }));

    const state = useOnboardingStore.getState();
    expect(state.activeTour).toBe("home");
    expect(state.currentTourStep).toBe(0);
  });

  it("dispara skipTour('home') al hacer clic en 'Omitir por ahora'", () => {
    render(<WelcomeModal />);

    fireEvent.click(screen.getByRole("button", { name: /Omitir por ahora/i }));

    const state = useOnboardingStore.getState();
    expect(state.tours.home).toBe(true);
    expect(state.activeTour).toBeNull();
  });

  it("ignora el cierre al presionar Escape o al hacer clic en el backdrop", () => {
    render(<WelcomeModal />);

    const dialog = screen.getByRole("dialog", { name: /¡Bienvenido a Chiripa!/i });
    expect(dialog).toBeInTheDocument();

    // Intentar cerrar con Escape
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.getByRole("dialog", { name: /¡Bienvenido a Chiripa!/i })).toBeInTheDocument();

    // Intentar cerrar con clic en el backdrop
    const backdrop = dialog.parentElement;
    expect(backdrop).not.toBeNull();
    if (backdrop) {
      fireEvent.mouseDown(backdrop);
    }
    expect(screen.getByRole("dialog", { name: /¡Bienvenido a Chiripa!/i })).toBeInTheDocument();

    // El estado del tour de home sigue sin completarse
    const state = useOnboardingStore.getState();
    expect(state.tours.home).toBe(false);
    expect(state.activeTour).toBeNull();
  });
});
