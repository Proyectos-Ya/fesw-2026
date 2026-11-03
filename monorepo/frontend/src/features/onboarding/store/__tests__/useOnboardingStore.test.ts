import { beforeEach, describe, expect, it } from "vitest";
import {
  ONBOARDING_STORAGE_KEY,
  useOnboardingStore,
} from "../useOnboardingStore";

describe("useOnboardingStore", () => {
  beforeEach(() => {
    window.localStorage.clear();
    useOnboardingStore.setState({
      hasCompletedOnboarding: false,
      isTourActive: false,
      currentTourStep: 0,
      isHelpCenterOpen: false,
      _hasHydrated: true,
    });
  });

  it("inicia con el estado por defecto para usuarios nuevos", () => {
    const state = useOnboardingStore.getState();
    expect(state.hasCompletedOnboarding).toBe(false);
    expect(state.isTourActive).toBe(false);
    expect(state.currentTourStep).toBe(0);
    expect(state.isHelpCenterOpen).toBe(false);
    expect(state._hasHydrated).toBe(true);
  });

  it("startTour activa el recorrido desde el paso 0 y cierra el centro de ayuda", () => {
    useOnboardingStore.setState({ isHelpCenterOpen: true, currentTourStep: 2 });

    useOnboardingStore.getState().startTour();

    const state = useOnboardingStore.getState();
    expect(state.isTourActive).toBe(true);
    expect(state.currentTourStep).toBe(0);
    expect(state.isHelpCenterOpen).toBe(false);
  });

  it("nextStep, prevStep y setTourStep actualizan currentTourStep de forma segura", () => {
    const store = useOnboardingStore.getState();

    store.startTour();
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

  it("skipTour detiene el tour y marca hasCompletedOnboarding como true", () => {
    useOnboardingStore.getState().startTour();
    useOnboardingStore.getState().setTourStep(1);

    useOnboardingStore.getState().skipTour();

    const state = useOnboardingStore.getState();
    expect(state.isTourActive).toBe(false);
    expect(state.hasCompletedOnboarding).toBe(true);
    expect(state.currentTourStep).toBe(0);
  });

  it("completeOnboarding finaliza el tour y persiste hasCompletedOnboarding en localStorage", () => {
    useOnboardingStore.getState().startTour();
    useOnboardingStore.getState().setTourStep(2);

    useOnboardingStore.getState().completeOnboarding();

    const state = useOnboardingStore.getState();
    expect(state.hasCompletedOnboarding).toBe(true);
    expect(state.isTourActive).toBe(false);
    expect(state.currentTourStep).toBe(0);

    const raw = window.localStorage.getItem(ONBOARDING_STORAGE_KEY);
    expect(raw).not.toBeNull();
    const parsed = JSON.parse(raw ?? "{}") as {
      state?: Record<string, unknown>;
    };
    expect(parsed.state).toEqual({
      hasCompletedOnboarding: true,
      isTourActive: false,
      currentTourStep: 0,
    });
    expect(parsed.state).not.toHaveProperty("isHelpCenterOpen");
  });

  it("openHelpCenter y closeHelpCenter controlan la visibilidad del Drawer lateral", () => {
    useOnboardingStore.getState().openHelpCenter();
    expect(useOnboardingStore.getState().isHelpCenterOpen).toBe(true);

    useOnboardingStore.getState().closeHelpCenter();
    expect(useOnboardingStore.getState().isHelpCenterOpen).toBe(false);
  });

  it("resetTour cierra el Centro de Ayuda y reinicia el recorrido desde el paso 0", () => {
    useOnboardingStore.setState({
      hasCompletedOnboarding: true,
      isTourActive: false,
      currentTourStep: 2,
      isHelpCenterOpen: true,
    });

    useOnboardingStore.getState().resetTour();

    const state = useOnboardingStore.getState();
    expect(state.isHelpCenterOpen).toBe(false);
    expect(state.isTourActive).toBe(true);
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
          hasCompletedOnboarding: true,
          isTourActive: false,
          currentTourStep: 2,
        },
        version: 0,
      }),
    );

    await useOnboardingStore.persist.rehydrate();

    const state = useOnboardingStore.getState();
    expect(state._hasHydrated).toBe(true);
    expect(state.hasCompletedOnboarding).toBe(true);
    expect(state.currentTourStep).toBe(2);
  });
});
