/** Un enlace vigente, tal como lo lista la ficha. La URL no vuelve a mostrarse. */
export interface ShareLink {
  id: string;
  /** ISO-8601 UTC con sufijo `Z`. */
  created_at: string;
  expires_at: string;
}

/** Solo la respuesta de creación trae la URL: en la base queda su hash. */
export interface CreatedShareLink extends ShareLink {
  url: string;
}

export interface SharedItem {
  name: string;
  description: string | null;
  quantity: number;
  unit_of_measure: string;
}

export type Recommendation = "Postular" | "Evaluar con cautela" | "No recomendado";

export interface SharedAnalysis {
  compatibility_score: number;
  recommendation: Recommendation;
  justification: string;
  updated_at: string;
}

/** Lo que ve un tercero al abrir el enlace, sin sesión. */
export interface SharedTender {
  code: string;
  name: string;
  description: string | null;
  status_code: string | null;
  is_closed: boolean;
  published_at: string;
  closing_at: string;
  buyer_name: string | null;
  buyer_unit: string;
  region: string | null;
  commune: string | null;
  available_amount_clp: number | null;
  items: SharedItem[];
  supplier_name: string | null;
  score_pct: number | null;
  analysis: SharedAnalysis | null;
  expires_at: string;
}

/** Por qué un enlace dejó de funcionar; viaja en `?motivo=` a `/enlace-caducado`. */
export type ExpiredReason = "caducado" | "revocado";

/** Los `code` con que el backend distingue los dos 410. */
export const SHARE_LINK_ERROR_CODES: Record<string, ExpiredReason> = {
  share_link_expired: "caducado",
  share_link_revoked: "revocado",
};
