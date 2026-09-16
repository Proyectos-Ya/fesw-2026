export interface TenderItem {
  id: string;
  tender_id: string;
  product_code: string;
  name: string;
  description: string | null;
  quantity: number;
  unit_of_measure: string;
}

export interface Tender {
  id: string;
  code: string;
  name: string;
  description: string | null;
  status_id: number;
  status_code: string | null;
  published_at: string;
  closing_at: string;
  last_change_at: string;
  buyer_rut: string;
  buyer_name: string | null;
  buyer_unit: string;
  region: string | null;
  province: string | null;
  commune: string | null;
  available_amount_clp: number | null;
  created_at: string;
  updated_at: string;
  items: TenderItem[];
  is_saved?: boolean;
}

export interface MatchingResult {
  id: string;
  supplier_id: string;
  tender_id: string;
  /** Nulo en los cálculos a pedido: no pasan por la búsqueda vectorial. */
  similarity_score: number | null;
  reranker_score: number | null;
  /** Nulo mientras nadie haya calculado la compatibilidad de esta licitación. */
  final_score: number | null;
  model_version: string;
  calculated_at: string;
  tender: Tender | null;
}

export interface DeepAnalysis {
  id: string;
  tender_id: string;
  supplier_id: string;
  compatibility_score: number;
  recommendation: "Postular" | "Evaluar con cautela" | "No recomendado";
  justification: string;
  prompt_instruction: string | null;
  created_at: string;
  updated_at: string;
  /** El perfil o la licitación cambiaron después de escribirse este análisis. */
  is_outdated?: boolean;
}

/** Respuesta de un cálculo de compatibilidad pedido por el usuario. */
export interface TenderScore {
  score_pct: number;
  calculated_at: string;
}

export type { TenderSearchParams, TenderSearchResult } from "@/features/search/types";

