import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import { markOnboardingCompletedApi } from "../services/onboardingService";

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
  setHasCompletedOnboarding: (completed: boolean) => void;
  markOnboardingAsCompletedAsync: () => Promise<void>;
}

export const useOnboardingStore = create<OnboardingState>()(
  persist(
    (set, get) => ({
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

      skipTour: () => {
        set({
          hasCompletedOnboarding: true,
          isTourActive: false,
          currentTourStep: 0,
        });
        void markOnboardingCompletedApi().catch((err) => {
          if (process.env.NODE_ENV !== "production") {
            console.warn("[Onboarding] Error syncing skipTour:", err);
          }
        });
      },

      completeOnboarding: () =>
        set({
          hasCompletedOnboarding: true,
          isTourActive: false,
          currentTourStep: 0,
        }),

      setHasCompletedOnboarding: (completed: boolean) =>
        set({
          hasCompletedOnboarding: completed,
        }),

      markOnboardingAsCompletedAsync: async () => {
        get().completeOnboarding();
        try {
          await markOnboardingCompletedApi();
        } catch (error) {
          if (process.env.NODE_ENV !== "production") {
            console.warn("[Onboarding] Error syncing onboarding status:", error);
          }
        }
      },

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
