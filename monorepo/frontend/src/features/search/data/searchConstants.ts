export const SEARCH_REGIONS: readonly string[] = [
  "Arica y Parinacota",
  "Tarapacá",
  "Antofagasta",
  "Atacama",
  "Coquimbo",
  "Valparaíso",
  "Libertador General Bernardo O'Higgins",
  "Maule",
  "Ñuble",
  "Biobío",
  "La Araucanía",
  "Los Ríos",
  "Los Lagos",
  "Aysén del General Carlos Ibáñez del Campo",
  "Magallanes y de la Antártica Chilena",
  "Metropolitana de Santiago",
];

/**
 * Estados por los que se puede filtrar: los que el backend acepta en
 * `status_codes`. Son los que tienen un id medido en Mercado Público; otro
 * valor responde 422.
 */
export type TenderStatusCode = "publicada" | "cerrada" | "desierta" | "cancelada";

export interface TenderStatusOption {
  value: TenderStatusCode;
  label: string;
}

export const TENDER_STATUS_OPTIONS: readonly TenderStatusOption[] = [
  { value: "publicada", label: "Vigente" },
  { value: "cerrada", label: "Cerrada" },
  { value: "desierta", label: "Desierta" },
  { value: "cancelada", label: "Cancelada" },
];

/**
 * Sin estado elegido se busca solo lo vigente. Además de ser a lo que se puede
 * postular, es lo único que el backend ordena por afinidad con la empresa.
 */
export const DEFAULT_STATUS_CODES: readonly TenderStatusCode[] = ["publicada"];

/**
 * Traducción del antiguo `availability` de la URL, para que los enlaces y las
 * búsquedas guardadas en sessionStorage sigan funcionando.
 */
export const LEGACY_AVAILABILITY_STATUSES: Readonly<
  Record<string, readonly TenderStatusCode[]>
> = {
  vigentes: ["publicada"],
  cerradas: ["cerrada", "desierta", "cancelada"],
};

export function isTenderStatusCode(value: string): value is TenderStatusCode {
  return TENDER_STATUS_OPTIONS.some((option) => option.value === value);
}

export const PAGE_SIZE = 20;
export const DEBOUNCE_MS = 350;
