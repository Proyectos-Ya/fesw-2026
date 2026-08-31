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

export type AvailabilityFilter = "vigentes" | "cerradas" | null;

export interface AvailabilityOption {
  value: "vigentes" | "cerradas";
  label: string;
}

export const AVAILABILITY_OPTIONS: readonly AvailabilityOption[] = [
  { value: "vigentes", label: "Vigentes" },
  { value: "cerradas", label: "Cerradas" },
];

export const PAGE_SIZE = 20;
export const DEBOUNCE_MS = 350;
