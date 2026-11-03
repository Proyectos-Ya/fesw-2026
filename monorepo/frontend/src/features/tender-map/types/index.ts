/**
 * Mapa de licitaciones (HU-22, #314). Espejo de `TenderMapResponse` del backend
 * (`GET /tenders/map`).
 */

/**
 * Qué tan exacto es el punto. `comuna` es aproximado: la dirección no se
 * encontró y el marcador va en la comuna del organismo.
 */
export type GeoPrecision = "direccion" | "comuna" | "no_encontrada";

export interface TenderMapPoint {
  id: string;
  name: string;
  buyer_name: string | null;
  delivery_address: string;
  closing_at: string;
  lat: number;
  lng: number;
  precision: GeoPrecision;
}

export interface TenderMapResult {
  /** Nombre canónico de la región, el mismo de `SEARCH_REGIONS`. */
  region: string;
  items: TenderMapPoint[];
  /** Cuántas cumplen; puede ser mayor que `items` si el tope dejó marcadores fuera. */
  total: number;
  is_truncated: boolean;
}
