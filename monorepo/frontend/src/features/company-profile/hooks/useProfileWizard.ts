"use client";

import { useReducer } from "react";
import type { ProfileData } from "../profileSchema";
import type { CompanyProfileImport } from "../services/supplierService";

export type WizardStep = 1 | 2 | 3 | 4;

interface WizardState {
  currentStep: WizardStep;
  data: Partial<ProfileData>;
  /** Datos importados desde el RUT; las palabras clave se ofrecen como sugerencias. */
  importedProfile: CompanyProfileImport | null;
}

type WizardAction =
  | { type: "NEXT"; payload: Partial<ProfileData> }
  | { type: "PREV" }
  | { type: "GO_TO"; payload: WizardStep }
  | { type: "IMPORT"; payload: CompanyProfileImport };

const initialState: WizardState = {
  currentStep: 1,
  data: {
    regions: [],
    sectors: [],
    keywords: [],
    certifications: [],
  },
  importedProfile: null,
};

function union(current: string[], added: string[]): string[] {
  return [...current, ...added.filter((value) => !current.includes(value))];
}

function reducer(state: WizardState, action: WizardAction): WizardState {
  switch (action.type) {
    case "NEXT":
      return {
        ...state,
        currentStep: Math.min(state.currentStep + 1, 4) as WizardStep,
        data: { ...state.data, ...action.payload },
      };
    case "PREV":
      return { ...state, currentStep: Math.max(state.currentStep - 1, 1) as WizardStep };
    case "GO_TO":
      return { ...state, currentStep: action.payload };
    case "IMPORT":
      // Los rubros se marcan de antemano (el usuario los desmarca en el paso 3);
      // las regiones las marca el formulario vivo del paso 2.
      return {
        ...state,
        importedProfile: action.payload,
        data: {
          ...state.data,
          sectors: union(state.data.sectors ?? [], action.payload.sectors),
        },
      };
  }
}

export function useProfileWizard() {
  const [state, dispatch] = useReducer(reducer, initialState);
  return {
    currentStep: state.currentStep,
    formData: state.data,
    importedProfile: state.importedProfile,
    totalSteps: 4 as const,
    nextStep: (data: Partial<ProfileData>) => dispatch({ type: "NEXT", payload: data }),
    prevStep: () => dispatch({ type: "PREV" }),
    goToStep: (step: WizardStep) => dispatch({ type: "GO_TO", payload: step }),
    applyImport: (profile: CompanyProfileImport) =>
      dispatch({ type: "IMPORT", payload: profile }),
  };
}
