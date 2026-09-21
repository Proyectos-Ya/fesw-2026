import { REGIONS as PROFILE_REGIONS } from "@/features/company-profile/data/regions";
import { SEARCH_REGIONS } from "./searchConstants";

/**
 * El perfil de empresa y el buscador nombran distinto a las mismas regiones:
 * el perfil usa la forma corta de uso corriente y el buscador el nombre
 * canónico, que es el único que el backend acepta en `/tenders/search` (compara
 * de forma estricta y responde 422 ante cualquier otro).
 *
 * Solo cuatro difieren; el resto coincide carácter por carácter.
 */
const EQUIVALENCIAS: Readonly<Record<string, string>> = {
  Metropolitana: "Metropolitana de Santiago",
  "O'Higgins": "Libertador General Bernardo O'Higgins",
  Aysén: "Aysén del General Carlos Ibáñez del Campo",
  Magallanes: "Magallanes y de la Antártica Chilena",
};

/** El nombre que entiende el buscador, o `null` si la región no se reconoce. */
export function toSearchRegion(profileRegion: string): string | null {
  const equivalente = EQUIVALENCIAS[profileRegion] ?? profileRegion;
  return SEARCH_REGIONS.includes(equivalente) ? equivalente : null;
}

/**
 * Traduce las regiones del perfil. Descarta en silencio las que no calzan: una
 * región desconocida haría fallar la búsqueda entera con un 422, y quedarse sin
 * buscador es peor que quedarse sin ese filtro.
 */
export function toSearchRegions(profileRegions: readonly string[]): string[] {
  const traducidas = profileRegions
    .map(toSearchRegion)
    .filter((region): region is string => region !== null);
  return [...new Set(traducidas)];
}

export { PROFILE_REGIONS };
