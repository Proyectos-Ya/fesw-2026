/**
 * Lista única de regiones del frontend. Usa el nombre canónico, el único que el
 * backend acepta en `/tenders/search` (compara de forma estricta y responde 422
 * ante cualquier otro). El perfil de empresa y el buscador leen esta misma lista.
 */
export const REGIONS: readonly string[] = [
  "Arica y Parinacota",
  "Tarapacá",
  "Antofagasta",
  "Atacama",
  "Coquimbo",
  "Valparaíso",
  "Metropolitana de Santiago",
  "Libertador General Bernardo O'Higgins",
  "Maule",
  "Ñuble",
  "Biobío",
  "La Araucanía",
  "Los Ríos",
  "Los Lagos",
  "Aysén del General Carlos Ibáñez del Campo",
  "Magallanes y de la Antártica Chilena",
];

/**
 * Los perfiles guardados antes de unificar la lista traen cuatro regiones con
 * su nombre corto. Se leen con esta tabla, solo al cargar; al guardar de nuevo
 * quedan con el nombre canónico y no hace falta migrar la base.
 */
const LEGACY_NAMES: Readonly<Record<string, string>> = {
  Metropolitana: "Metropolitana de Santiago",
  "O'Higgins": "Libertador General Bernardo O'Higgins",
  Aysén: "Aysén del General Carlos Ibáñez del Campo",
  Magallanes: "Magallanes y de la Antártica Chilena",
};

/** El nombre canónico de la región, o `null` si no se reconoce. */
export function toCanonicalRegion(name: string): string | null {
  const canonical = LEGACY_NAMES[name] ?? name;
  return REGIONS.includes(canonical) ? canonical : null;
}

/**
 * Convierte una lista guardada. Descarta en silencio las desconocidas: una
 * región fuera de la lista haría fallar la búsqueda entera con un 422, y
 * quedarse sin buscador es peor que quedarse sin ese filtro.
 */
export function toCanonicalRegions(names: readonly string[]): string[] {
  const canonical = names
    .map(toCanonicalRegion)
    .filter((region): region is string => region !== null);
  return [...new Set(canonical)];
}
