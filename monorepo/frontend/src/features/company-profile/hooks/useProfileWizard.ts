"use client";

import { useReducer } from "react";
import { formatRut, type ProfileData } from "../profileSchema";
import type { CompanyProfileImport } from "../services/supplierService";
import { REGIONS } from "../data/regions";
import { SECTORS } from "../data/sectors";

export type WizardStep = 1 | 2 | 3 | 4;

export type ImportedField = "legal_name" | "regions" | "sectors";
export type ReviewStatus = "pending" | "editing" | "confirmed";

interface ImportReview {
  /** RUT de la última importación, para detectar la reimportación con otro RUT. */
  rut: string | null;
  status: Partial<Record<ImportedField, ReviewStatus>>;
  /** Lo que sumó la importación. Borrar quita solo esto. */
  added: { regions: string[]; sectors: string[] };
}

/** Campos importados que se revisan en cada paso. */
const REVIEWED_FIELD_BY_STEP: Partial<Record<WizardStep, ImportedField>> = {
  1: "legal_name",
  2: "regions",
  3: "sectors",
};

interface WizardState {
  currentStep: WizardStep;
  data: Partial<ProfileData>;
  /** Datos importados desde el RUT; las palabras clave se ofrecen como sugerencias. */
  importedProfile: CompanyProfileImport | null;
  importReview: ImportReview;
  /** Sugerencias de palabras clave que el usuario descartó; sobreviven al cambio de paso. */
  dismissedKeywords: string[];
}

type WizardAction =
  | { type: "NEXT"; payload: Partial<ProfileData> }
  | { type: "PREV" }
  | { type: "GO_TO"; payload: WizardStep }
  | { type: "IMPORT"; payload: CompanyProfileImport }
  | { type: "CONFIRM_FIELD"; payload: ImportedField }
  | { type: "EDIT_FIELD"; payload: ImportedField }
  | { type: "CLEAR_FIELD"; payload: ImportedField }
  | { type: "DISCARD_IMPORT" }
  | { type: "DISMISS_KEYWORD"; payload: string };

const initialState: WizardState = {
  currentStep: 1,
  data: {
    regions: [],
    sectors: [],
    keywords: [],
    certifications: [],
  },
  importedProfile: null,
  importReview: { rut: null, status: {}, added: { regions: [], sectors: [] } },
  dismissedKeywords: [],
};

const normalizeKeyword = (keyword: string) => keyword.trim().toLocaleLowerCase("es");

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
      return applyImport(state, action.payload);
    case "CONFIRM_FIELD":
      return setReviewStatus(state, action.payload, "confirmed");
    case "EDIT_FIELD":
      return setReviewStatus(state, action.payload, "editing");
    case "CLEAR_FIELD":
      return clearField(state, action.payload);
    case "DISCARD_IMPORT":
      return discardImport(state);
    case "DISMISS_KEYWORD": {
      const taken = new Set(state.dismissedKeywords.map(normalizeKeyword));
      if (taken.has(normalizeKeyword(action.payload))) return state;
      return { ...state, dismissedKeywords: [...state.dismissedKeywords, action.payload] };
    }
  }
}

function applyImport(state: WizardState, profile: CompanyProfileImport): WizardState {
  const rut = formatRut(profile.rut);
  const isOtherRut = state.importReview.rut !== null && state.importReview.rut !== rut;
  const status: ImportReview["status"] = isOtherRut ? {} : { ...state.importReview.status };
  const previous = isOtherRut
    ? { legal_name: "", regions: [], sectors: [] }
    : {
        legal_name: state.data.legal_name,
        regions: state.data.regions ?? [],
        sectors: state.data.sectors ?? [],
      };
  const previousAdded = isOtherRut ? { regions: [], sectors: [] } : state.importReview.added;

  const importedRegions = profile.regions.filter((region) => REGIONS.includes(region));
  const importedSectors = profile.sectors.filter((sector) => SECTORS.includes(sector));
  const regions = union(previous.regions, importedRegions);
  const sectors = union(previous.sectors, importedSectors);

  const legalName = profile.legal_name.trim();
  if (legalName) status.legal_name = "pending";
  if (importedRegions.length > 0) status.regions = "pending";
  if (importedSectors.length > 0) status.sectors = "pending";

  return {
    ...state,
    importedProfile: profile,
    data: {
      ...state.data,
      legal_name: legalName || previous.legal_name,
      regions,
      sectors,
    },
    importReview: {
      rut,
      status,
      added: {
        regions: union(
          previousAdded.regions.filter((region) => regions.includes(region)),
          importedRegions.filter((region) => !previous.regions.includes(region)),
        ),
        sectors: union(
          previousAdded.sectors.filter((sector) => sectors.includes(sector)),
          importedSectors.filter((sector) => !previous.sectors.includes(sector)),
        ),
      },
    },
  };
}

function setReviewStatus(
  state: WizardState,
  field: ImportedField,
  status: ReviewStatus,
): WizardState {
  // Un campo que la importación no tocó no está en revisión.
  if (!state.importReview.status[field]) return state;
  return {
    ...state,
    importReview: {
      ...state.importReview,
      status: { ...state.importReview.status, [field]: status },
    },
  };
}

function clearField(state: WizardState, field: ImportedField): WizardState {
  const status = { ...state.importReview.status };
  delete status[field];
  const importReview = { ...state.importReview, status };
  if (field === "legal_name") {
    return { ...state, data: { ...state.data, legal_name: "" }, importReview };
  }
  const added = state.importReview.added[field];
  return {
    ...state,
    data: { ...state.data, [field]: (state.data[field] ?? []).filter((v) => !added.includes(v)) },
    importReview: { ...importReview, added: { ...state.importReview.added, [field]: [] } },
  };
}

/**
 * El usuario cambió el RUT después de importar: lo importado es de otra empresa.
 * Se quita aunque ya esté confirmado, y se conserva lo que el usuario eligió a mano.
 */
function discardImport(state: WizardState): WizardState {
  const { status, added } = state.importReview;
  return {
    ...state,
    importedProfile: null,
    data: {
      ...state.data,
      legal_name: status.legal_name ? "" : state.data.legal_name,
      regions: (state.data.regions ?? []).filter((region) => !added.regions.includes(region)),
      sectors: (state.data.sectors ?? []).filter((sector) => !added.sectors.includes(sector)),
    },
    importReview: initialState.importReview,
  };
}

export function useProfileWizard() {
  const [state, dispatch] = useReducer(reducer, initialState);
  return {
    currentStep: state.currentStep,
    formData: state.data,
    importedProfile: state.importedProfile,
    importReview: state.importReview,
    dismissedKeywords: state.dismissedKeywords,
    totalSteps: 4 as const,
    nextStep: (data: Partial<ProfileData>) => dispatch({ type: "NEXT", payload: data }),
    prevStep: () => dispatch({ type: "PREV" }),
    goToStep: (step: WizardStep) => dispatch({ type: "GO_TO", payload: step }),
    applyImport: (profile: CompanyProfileImport) =>
      dispatch({ type: "IMPORT", payload: profile }),
    confirmField: (field: ImportedField) => dispatch({ type: "CONFIRM_FIELD", payload: field }),
    editField: (field: ImportedField) => dispatch({ type: "EDIT_FIELD", payload: field }),
    clearField: (field: ImportedField) => dispatch({ type: "CLEAR_FIELD", payload: field }),
    discardImport: () => dispatch({ type: "DISCARD_IMPORT" }),
    /** Verdadero si el paso tiene un campo importado sin confirmar. */
    isStepBlocked: (step: WizardStep) => {
      const field = REVIEWED_FIELD_BY_STEP[step];
      const status = field && state.importReview.status[field];
      return status === "pending" || status === "editing";
    },
    dismissKeyword: (keyword: string) => dispatch({ type: "DISMISS_KEYWORD", payload: keyword }),
  };
}
