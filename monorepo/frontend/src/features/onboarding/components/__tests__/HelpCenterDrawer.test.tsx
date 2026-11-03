import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { useOnboardingStore } from "../../store/useOnboardingStore";
import { HelpCenterDrawer } from "../HelpCenterDrawer";

describe("HelpCenterDrawer", () => {
  beforeEach(() => {
    window.localStorage.clear();
    useOnboardingStore.setState({
      hasCompletedOnboarding: true,
      isTourActive: false,
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

  it("muestra el cajón con las guías estáticas y el botón 'Reiniciar tour interactivo' cuando está abierto", () => {
    useOnboardingStore.setState({ isHelpCenterOpen: true });

    render(<HelpCenterDrawer />);

    expect(
      screen.getByRole("dialog", { name: /Centro de Ayuda/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Reiniciar tour interactivo/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Cómo funciona el matching/i)).toBeInTheDocument();
    expect(screen.getByText(/Búsqueda manual/i)).toBeInTheDocument();
    expect(screen.getByText(/Guardados y Tablero Kanban/i)).toBeInTheDocument();
    expect(screen.getByText(/Alertas y notificaciones/i)).toBeInTheDocument();
  });

  it("ejecuta resetTour al hacer clic en 'Reiniciar tour interactivo'", () => {
    useOnboardingStore.setState({
      isHelpCenterOpen: true,
      isTourActive: false,
      currentTourStep: 2,
    });

    render(<HelpCenterDrawer />);

    fireEvent.click(
      screen.getByRole("button", { name: /Reiniciar tour interactivo/i }),
    );

    const state = useOnboardingStore.getState();
    expect(state.isHelpCenterOpen).toBe(false);
    expect(state.isTourActive).toBe(true);
    expect(state.currentTourStep).toBe(0);
  });

  it("cierra el cajón al presionar el botón de cerrar o la tecla Escape", () => {
    useOnboardingStore.setState({ isHelpCenterOpen: true });

    render(<HelpCenterDrawer />);

    fireEvent.keyDown(document, { key: "Escape" });
    expect(useOnboardingStore.getState().isHelpCenterOpen).toBe(false);
  });
});
