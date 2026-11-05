import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import {
  markOnboardingCompletedApi,
  type TourName,
} from "../services/onboardingService";

export const ONBOARDING_STORAGE_KEY = "chiripa_onboarding_state";

export interface TourProgress {
  home: boolean;
  detail: boolean;
  draft: boolean;
}

interface PersistedOnboardingSlice {
  tours: TourProgress;
  activeTour: TourName | null;
  currentTourStep: number;
}

export interface OnboardingState extends PersistedOnboardingSlice {
  isHelpCenterOpen: boolean;
  _hasHydrated: boolean;
  startTour: (tourName: TourName) => void;
  nextStep: () => void;
  prevStep: () => void;
  setTourStep: (step: number) => void;
  skipTour: (tourName?: TourName) => void;
  completeTour: (tourName: TourName) => void;
  resetTour: (tourName: TourName) => void;
  openHelpCenter: () => void;
  closeHelpCenter: () => void;
  setHasHydrated: (hydrated: boolean) => void;
  setToursStatus: (tours: Partial<TourProgress>) => void;
  markOnboardingAsCompletedAsync: (tourName: TourName) => Promise<void>;
}

export const useOnboardingStore = create<OnboardingState>()(
  persist(
    (set, get) => ({
      tours: {
        home: false,
        detail: false,
        draft: false,
      },
      activeTour: null,
      currentTourStep: 0,
      isHelpCenterOpen: false,
      _hasHydrated: false,

      startTour: (tourName: TourName) =>
        set({
          activeTour: tourName,
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

      skipTour: (tourName?: TourName) => {
        const targetTour = tourName ?? get().activeTour ?? "home";
        set((state) => ({
          tours: {
            ...state.tours,
            [targetTour]: true,
          },
          activeTour: null,
          currentTourStep: 0,
        }));
        void markOnboardingCompletedApi(targetTour).catch((err) => {
          if (process.env.NODE_ENV !== "production") {
            console.warn("[Onboarding] Error syncing skipTour:", err);
          }
        });
      },

      completeTour: (tourName: TourName) =>
        set((state) => ({
          tours: {
            ...state.tours,
            [tourName]: true,
          },
          activeTour: null,
          currentTourStep: 0,
        })),

      setToursStatus: (toursUpdate: Partial<TourProgress>) =>
        set((state) => ({
          tours: {
            home: toursUpdate.home ?? state.tours.home,
            detail: toursUpdate.detail ?? state.tours.detail,
            draft: toursUpdate.draft ?? state.tours.draft,
          },
        })),

      markOnboardingAsCompletedAsync: async (tourName: TourName) => {
        get().completeTour(tourName);
        try {
          await markOnboardingCompletedApi(tourName);
        } catch (error) {
          if (process.env.NODE_ENV !== "production") {
            console.warn("[Onboarding] Error syncing onboarding status:", error);
          }
        }
      },

      resetTour: (tourName: TourName) =>
        set({
          isHelpCenterOpen: false,
          activeTour: tourName,
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
        tours: state.tours,
        activeTour: state.activeTour,
        currentTourStep: state.currentTourStep,
      }),
      onRehydrateStorage: () => (state) => {
        state?.setHasHydrated(true);
      },
    },
  ),
);
