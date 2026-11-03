import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

export const ONBOARDING_STORAGE_KEY = "chiripa_onboarding_state";

interface PersistedOnboardingSlice {
  hasCompletedOnboarding: boolean;
  isTourActive: boolean;
  currentTourStep: number;
}

export interface OnboardingState extends PersistedOnboardingSlice {
  isHelpCenterOpen: boolean;
  _hasHydrated: boolean;
  startTour: () => void;
  nextStep: () => void;
  prevStep: () => void;
  setTourStep: (step: number) => void;
  skipTour: () => void;
  completeOnboarding: () => void;
  resetTour: () => void;
  openHelpCenter: () => void;
  closeHelpCenter: () => void;
  setHasHydrated: (hydrated: boolean) => void;
}

export const useOnboardingStore = create<OnboardingState>()(
  persist(
    (set) => ({
      hasCompletedOnboarding: false,
      isTourActive: false,
      currentTourStep: 0,
      isHelpCenterOpen: false,
      _hasHydrated: false,

      startTour: () =>
        set({
          isTourActive: true,
          currentTourStep: 0,
          isHelpCenterOpen: false,
        }),

      nextStep: () =>
        set((state) => ({
          currentTourStep: state.currentTourStep + 1,
        })),

      prevStep: () =>
        set((state) => ({
          currentTourStep: Math.max(0, state.currentTourStep - 1),
        })),

      setTourStep: (step: number) =>
        set({
          currentTourStep: Math.max(0, step),
        }),

      skipTour: () =>
        set({
          hasCompletedOnboarding: true,
          isTourActive: false,
          currentTourStep: 0,
        }),

      completeOnboarding: () =>
        set({
          hasCompletedOnboarding: true,
          isTourActive: false,
          currentTourStep: 0,
        }),

      resetTour: () =>
        set({
          isHelpCenterOpen: false,
          isTourActive: true,
          currentTourStep: 0,
        }),

      openHelpCenter: () =>
        set({
          isHelpCenterOpen: true,
        }),

      closeHelpCenter: () =>
        set({
          isHelpCenterOpen: false,
        }),

      setHasHydrated: (hydrated: boolean) =>
        set({
          _hasHydrated: hydrated,
        }),
    }),
    {
      name: ONBOARDING_STORAGE_KEY,
      storage: createJSONStorage(() => window.localStorage),
      partialize: (state): PersistedOnboardingSlice => ({
        hasCompletedOnboarding: state.hasCompletedOnboarding,
        isTourActive: state.isTourActive,
        currentTourStep: state.currentTourStep,
      }),
      onRehydrateStorage: () => (state) => {
        state?.setHasHydrated(true);
      },
    },
  ),
);
