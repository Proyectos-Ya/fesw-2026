import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useOnboardingStore } from "../../store/useOnboardingStore";
import { HelpCenterDrawer } from "../HelpCenterDrawer";

const mockPush = vi.fn();
let mockPathname = "/";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
  usePathname: () => mockPathname,
}));

describe("HelpCenterDrawer", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockPathname = "/";
    window.localStorage.clear();
    useOnboardingStore.setState({
      tours: {
        home: true,
        detail: false,
        draft: false,
      },
      activeTour: null,
      currentTourStep: 0,
      isHelpCenterOpen: false,
      _hasHydrated: true,
    });
  });

  it("no muestra el cajón cuando isHelpCenterOpen es false", () => {
    render(<HelpCenterDrawer />);

    expect(
      screen.queryByRole("dialog", { name: /Centro de Ayuda/i }),
    ).not.toBeInTheDocument();
  });

  it("muestra el cajón con guías y botón dinámico 'Tour de Inicio' en la raíz", () => {
    useOnboardingStore.setState({ isHelpCenterOpen: true });
    mockPathname = "/";

    render(<HelpCenterDrawer />);

    expect(
      screen.getByRole("dialog", { name: /Centro de Ayuda/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("Tour de Inicio")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Reiniciar tour de inicio/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Cómo funciona el matching/i)).toBeInTheDocument();
  });

  it("muestra 'Tour de Licitación' en rutas de detalle de licitación", () => {
    useOnboardingStore.setState({ isHelpCenterOpen: true });
    mockPathname = "/matches/licitacion-123";

    render(<HelpCenterDrawer />);

    expect(screen.getByText("Tour de Licitación")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Reiniciar tour de licitación/i }),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: /Reiniciar tour de licitación/i }),
    );

    const state = useOnboardingStore.getState();
    expect(state.isHelpCenterOpen).toBe(false);
    expect(state.activeTour).toBe("detail");
    expect(state.currentTourStep).toBe(0);
  });

  it("muestra 'Tour de Postulación' en rutas de propuesta o cotización", () => {
    useOnboardingStore.setState({ isHelpCenterOpen: true });
    mockPathname = "/matches/licitacion-123/postulacion";

    render(<HelpCenterDrawer />);

    expect(screen.getByText("Tour de Postulación")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Reiniciar tour de postulación/i }),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: /Reiniciar tour de postulación/i }),
    );

    const state = useOnboardingStore.getState();
    expect(state.isHelpCenterOpen).toBe(false);
    expect(state.activeTour).toBe("draft");
    expect(state.currentTourStep).toBe(0);
  });

  it("redirige a '/' si el usuario reinicia el Tour de Inicio desde otra pantalla como '/buscar'", () => {
    useOnboardingStore.setState({ isHelpCenterOpen: true });
    mockPathname = "/buscar";

    render(<HelpCenterDrawer />);

    fireEvent.click(
      screen.getByRole("button", { name: /Reiniciar tour de inicio/i }),
    );

    expect(mockPush).toHaveBeenCalledWith("/");
    expect(useOnboardingStore.getState().activeTour).toBe("home");
  });

  it("cierra el cajón al presionar la tecla Escape", () => {
    useOnboardingStore.setState({ isHelpCenterOpen: true });

    render(<HelpCenterDrawer />);

    fireEvent.keyDown(document, { key: "Escape" });
    expect(useOnboardingStore.getState().isHelpCenterOpen).toBe(false);
  });
});
