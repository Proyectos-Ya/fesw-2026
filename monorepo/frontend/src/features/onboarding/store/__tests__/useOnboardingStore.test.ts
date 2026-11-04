import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  ONBOARDING_STORAGE_KEY,
  useOnboardingStore,
} from "../useOnboardingStore";

const mockMarkOnboardingCompletedApi = vi.fn().mockResolvedValue({
  id: "u-1",
  tour_home_completed: true,
  tour_detail_completed: false,
  tour_draft_completed: false,
});
vi.mock("../../services/onboardingService", () => ({
  markOnboardingCompletedApi: (tourName: string) =>
    mockMarkOnboardingCompletedApi(tourName),
}));

describe("useOnboardingStore", () => {
  beforeEach(() => {
    vi.clearAllMocks();
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
  });

  it("inicia con el estado por defecto para usuarios nuevos", () => {
    const state = useOnboardingStore.getState();
    expect(state.tours).toEqual({ home: false, detail: false, draft: false });
    expect(state.activeTour).toBeNull();
    expect(state.currentTourStep).toBe(0);
    expect(state.isHelpCenterOpen).toBe(false);
    expect(state._hasHydrated).toBe(true);
  });

  it("startTour activa el recorrido especificado desde el paso 0 y cierra el centro de ayuda", () => {
    useOnboardingStore.setState({ isHelpCenterOpen: true, currentTourStep: 2 });

    useOnboardingStore.getState().startTour("home");

    const state = useOnboardingStore.getState();
    expect(state.activeTour).toBe("home");
    expect(state.currentTourStep).toBe(0);
    expect(state.isHelpCenterOpen).toBe(false);
  });

  it("nextStep, prevStep y setTourStep actualizan currentTourStep de forma segura", () => {
    const store = useOnboardingStore.getState();

    store.startTour("home");
    expect(useOnboardingStore.getState().currentTourStep).toBe(0);

    store.prevStep();
    expect(useOnboardingStore.getState().currentTourStep).toBe(0);

    store.nextStep();
    expect(useOnboardingStore.getState().currentTourStep).toBe(1);

    store.setTourStep(2);
    expect(useOnboardingStore.getState().currentTourStep).toBe(2);

    store.prevStep();
    expect(useOnboardingStore.getState().currentTourStep).toBe(1);
  });

  it("skipTour detiene el tour y marca el tour correspondiente como completado", () => {
    useOnboardingStore.getState().startTour("home");
    useOnboardingStore.getState().setTourStep(1);

    useOnboardingStore.getState().skipTour("home");

    const state = useOnboardingStore.getState();
    expect(state.activeTour).toBeNull();
    expect(state.tours.home).toBe(true);
    expect(state.currentTourStep).toBe(0);
    expect(mockMarkOnboardingCompletedApi).toHaveBeenCalledWith("home");
  });

  it("completeTour finaliza el tour y persiste en localStorage", () => {
    useOnboardingStore.getState().startTour("detail");
    useOnboardingStore.getState().setTourStep(1);

    useOnboardingStore.getState().completeTour("detail");

    const state = useOnboardingStore.getState();
    expect(state.tours.detail).toBe(true);
    expect(state.activeTour).toBeNull();
    expect(state.currentTourStep).toBe(0);

    const raw = window.localStorage.getItem(ONBOARDING_STORAGE_KEY);
    expect(raw).not.toBeNull();
    const parsed = JSON.parse(raw ?? "{}") as {
      state?: Record<string, unknown>;
    };
    expect(parsed.state).toEqual({
      tours: { home: false, detail: true, draft: false },
      activeTour: null,
      currentTourStep: 0,
    });
  });

  it("openHelpCenter y closeHelpCenter controlan la visibilidad del Drawer lateral", () => {
    useOnboardingStore.getState().openHelpCenter();
    expect(useOnboardingStore.getState().isHelpCenterOpen).toBe(true);

    useOnboardingStore.getState().closeHelpCenter();
    expect(useOnboardingStore.getState().isHelpCenterOpen).toBe(false);
  });

  it("resetTour cierra el Centro de Ayuda y reinicia el recorrido específico desde el paso 0", () => {
    useOnboardingStore.setState({
      tours: { home: true, detail: false, draft: false },
      activeTour: null,
      currentTourStep: 2,
      isHelpCenterOpen: true,
    });

    useOnboardingStore.getState().resetTour("home");

    const state = useOnboardingStore.getState();
    expect(state.isHelpCenterOpen).toBe(false);
    expect(state.activeTour).toBe("home");
    expect(state.currentTourStep).toBe(0);
  });

  it("setHasHydrated actualiza la bandera de hidratación SSR", () => {
    useOnboardingStore.getState().setHasHydrated(false);
    expect(useOnboardingStore.getState()._hasHydrated).toBe(false);

    useOnboardingStore.getState().setHasHydrated(true);
    expect(useOnboardingStore.getState()._hasHydrated).toBe(true);
  });

  it("rehidrata desde localStorage y activa _hasHydrated automáticamente", async () => {
    useOnboardingStore.setState({ _hasHydrated: false });
    window.localStorage.setItem(
      ONBOARDING_STORAGE_KEY,
      JSON.stringify({
        state: {
          tours: { home: true, detail: false, draft: false },
          activeTour: null,
          currentTourStep: 2,
        },
        version: 0,
      }),
    );

    await useOnboardingStore.persist.rehydrate();

    const state = useOnboardingStore.getState();
    expect(state._hasHydrated).toBe(true);
    expect(state.tours.home).toBe(true);
    expect(state.currentTourStep).toBe(2);
  });

  it("setToursStatus actualiza el estado de tours de forma selectiva", () => {
    useOnboardingStore.getState().setToursStatus({ home: true });
    expect(useOnboardingStore.getState().tours.home).toBe(true);
    expect(useOnboardingStore.getState().tours.detail).toBe(false);

    useOnboardingStore.getState().setToursStatus({ detail: true, draft: true });
    expect(useOnboardingStore.getState().tours.detail).toBe(true);
    expect(useOnboardingStore.getState().tours.draft).toBe(true);
  });

  it("markOnboardingAsCompletedAsync actualiza optimisticamente y llama a la API con el nombre del tour", async () => {
    useOnboardingStore.setState({
      activeTour: "draft",
      currentTourStep: 1,
    });

    await useOnboardingStore.getState().markOnboardingAsCompletedAsync("draft");

    const state = useOnboardingStore.getState();
    expect(state.tours.draft).toBe(true);
    expect(state.activeTour).toBeNull();
    expect(state.currentTourStep).toBe(0);
    expect(mockMarkOnboardingCompletedApi).toHaveBeenCalledWith("draft");
  });
});
