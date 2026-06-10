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
  province: string | null;
  available_amount_clp: number | null;
  created_at: string;
  updated_at: string;
  items: TenderItem[];
}

export interface MatchingResult {
  id: string;
  supplier_id: string;
  tender_id: string;
  similarity_score: number;
  reranker_score: number | null;
  final_score: number;
  model_version: string;
  calculated_at: string;
  tender: Tender | null;
}
