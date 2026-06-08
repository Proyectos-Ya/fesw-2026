"use client";

import { useReducer } from "react";
import type { ProfileData } from "../profileSchema";

export type WizardStep = 1 | 2 | 3 | 4;

interface WizardState {
  currentStep: WizardStep;
  data: Partial<ProfileData>;
}

type WizardAction =
  | { type: "NEXT"; payload: Partial<ProfileData> }
  | { type: "PREV" }
  | { type: "GO_TO"; payload: WizardStep };

const initialState: WizardState = {
  currentStep: 1,
  data: {
    regions: [],
    sectors: [],
    keywords: [],
    certifications: [],
  },
};

function reducer(state: WizardState, action: WizardAction): WizardState {
  switch (action.type) {
    case "NEXT":
      return {
        currentStep: Math.min(state.currentStep + 1, 4) as WizardStep,
        data: { ...state.data, ...action.payload },
      };
    case "PREV":
      return { ...state, currentStep: Math.max(state.currentStep - 1, 1) as WizardStep };
    case "GO_TO":
      return { ...state, currentStep: action.payload };
  }
}

export function useProfileWizard() {
  const [state, dispatch] = useReducer(reducer, initialState);
  return {
    currentStep: state.currentStep,
    formData: state.data,
    totalSteps: 4 as const,
    nextStep: (data: Partial<ProfileData>) => dispatch({ type: "NEXT", payload: data }),
    prevStep: () => dispatch({ type: "PREV" }),
    goToStep: (step: WizardStep) => dispatch({ type: "GO_TO", payload: step }),
  };
}
