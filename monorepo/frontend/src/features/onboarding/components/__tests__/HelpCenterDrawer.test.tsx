import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useOnboardingStore } from "../../store/useOnboardingStore";
import {
  HelpCenterDrawer,
  getSortedCategories,
  HELP_CATEGORIES,
} from "../HelpCenterDrawer";

const mockPush = vi.fn();
let mockPathname = "/";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
  usePathname: () => mockPathname,
}));

describe("getSortedCategories", () => {
  it("prioriza 'navigation' en la ruta raíz '/'", () => {
    const sorted = getSortedCategories("/");
    expect(sorted[0]?.id).toBe("navigation");
  });

  it("prioriza 'navigation' en rutas de búsqueda '/buscar'", () => {
    const sorted = getSortedCategories("/buscar");
    expect(sorted[0]?.id).toBe("navigation");
  });

  it("prioriza 'profile' en rutas de empresa y perfil", () => {
    const sortedEmpresa = getSortedCategories("/empresa");
    expect(sortedEmpresa[0]?.id).toBe("profile");

    const sortedPerfil = getSortedCategories("/perfil");
    expect(sortedPerfil[0]?.id).toBe("profile");
  });

  it("prioriza 'detail' en rutas de detalle de licitación '/matches/123'", () => {
    const sorted = getSortedCategories("/matches/licitacion-123");
    expect(sorted[0]?.id).toBe("detail");
  });

  it("prioriza 'draft' sobre 'detail' en rutas de postulación o cotización", () => {
    const sortedPostulacion = getSortedCategories("/matches/licitacion-123/postulacion");
    expect(sortedPostulacion[0]?.id).toBe("draft");

    const sortedCotizacion = getSortedCategories("/matches/licitacion-123/cotizacion");
    expect(sortedCotizacion[0]?.id).toBe("draft");
  });

  it("contiene todas las categorías de HELP_CATEGORIES sin duplicados", () => {
    const sorted = getSortedCategories("/matches/licitacion-123");
    expect(sorted).toHaveLength(HELP_CATEGORIES.length);
    const ids = sorted.map((c) => c.id);
    expect(new Set(ids).size).toBe(HELP_CATEGORIES.length);
  });
});

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

  it("muestra el cajón con botón dinámico 'Tour de Inicio' en la raíz y categorías en acordeón", () => {
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
    expect(screen.getByText("Navegación por Chiripa")).toBeInTheDocument();
    expect(screen.getByText("Mi perfil de empresa")).toBeInTheDocument();
    expect(screen.getByText("Vista detallada de licitaciones")).toBeInTheDocument();
    expect(screen.getByText("Borrador y Cotizador")).toBeInTheDocument();
  });

  it("auto-expande la categoría prioritaria (índice 0) por defecto y colapsa las demás", () => {
    useOnboardingStore.setState({ isHelpCenterOpen: true });
    mockPathname = "/";

    const { container } = render(<HelpCenterDrawer />);

    const details = container.querySelectorAll('[aria-label="Categorías de ayuda"] > details');
    expect(details).toHaveLength(4);

    // El primer acordeón (Navegación por Chiripa) debe estar abierto
    expect(details[0]).toHaveAttribute("open");
    expect(details[1]).not.toHaveAttribute("open");
    expect(details[2]).not.toHaveAttribute("open");
    expect(details[3]).not.toHaveAttribute("open");
  });

  it("muestra los 5 sub-desplegables de navegación (Inicio, Buscar, Matches, Guardados, Tablero)", () => {
    useOnboardingStore.setState({ isHelpCenterOpen: true });
    mockPathname = "/";

    render(<HelpCenterDrawer />);

    expect(screen.getByText("Inicio")).toBeInTheDocument();
    expect(screen.getByText("Buscar")).toBeInTheDocument();
    expect(screen.getByText("Matches")).toBeInTheDocument();
    expect(screen.getByText("Guardados")).toBeInTheDocument();
    expect(screen.getByText("Tablero (Kanban)")).toBeInTheDocument();

    expect(
      screen.getByText(/Resumen diario con tus mejores recomendaciones/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Explorador manual de Mercado Público/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Catálogo completo de licitaciones afines a tu rubro/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Tu buzón de licitaciones pre-seleccionadas/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Espacio de trabajo visual\. Organiza tu proceso/i),
    ).toBeInTheDocument();
  });

  it("auto-expande 'detail' cuando la ruta es una licitación", () => {
    useOnboardingStore.setState({ isHelpCenterOpen: true });
    mockPathname = "/matches/licitacion-456";

    const { container } = render(<HelpCenterDrawer />);

    const details = container.querySelectorAll('[aria-label="Categorías de ayuda"] > details');
    expect(details[0]).toHaveAttribute("open");
    expect(details[0]).toHaveTextContent("Vista detallada de licitaciones");
    expect(details[1]).not.toHaveAttribute("open");
  });

  it("permite alternar el acordeón al hacer clic en el encabezado", () => {
    useOnboardingStore.setState({ isHelpCenterOpen: true });
    mockPathname = "/";

    const { container } = render(<HelpCenterDrawer />);

    const details = container.querySelectorAll('[aria-label="Categorías de ayuda"] > details');
    expect(details[0]).toHaveAttribute("open");
    expect(details[1]).not.toHaveAttribute("open");

    // Clic en la segunda categoría (Mi perfil de empresa)
    const summaryProfile = details[1]?.querySelector("summary");
    expect(summaryProfile).not.toBeNull();
    if (summaryProfile) {
      fireEvent.click(summaryProfile);
    }

    // Ahora la categoría perfil debe estar abierta y la de navegación cerrada
    expect(details[0]).not.toHaveAttribute("open");
    expect(details[1]).toHaveAttribute("open");

    // Clic nuevamente en la categoría abierta para colapsarla
    if (summaryProfile) {
      fireEvent.click(summaryProfile);
    }
    expect(details[1]).not.toHaveAttribute("open");
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
