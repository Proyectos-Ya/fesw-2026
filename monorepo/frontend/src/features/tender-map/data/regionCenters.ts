/**
 * Dónde se centra el mapa para cada región (HU-22, #314): su capital regional,
 * con un zoom que deja ver la región entera o casi. Así el mapa se ubica en la
 * zona aunque no haya ningún marcador.
 *
 * Las claves son los nombres canónicos de `SEARCH_REGIONS`; los del perfil se
 * traducen antes con `toSearchRegion`.
 */

export interface RegionCenter {
  lat: number;
  lng: number;
  zoom: number;
}

export const REGION_CENTERS: Readonly<Record<string, RegionCenter>> = {
  "Arica y Parinacota": { lat: -18.4783, lng: -70.3126, zoom: 8 },
  Tarapacá: { lat: -20.2133, lng: -70.1503, zoom: 7 },
  Antofagasta: { lat: -23.6509, lng: -70.3975, zoom: 6 },
  Atacama: { lat: -27.3668, lng: -70.3323, zoom: 7 },
  Coquimbo: { lat: -29.9045, lng: -71.2489, zoom: 7 },
  Valparaíso: { lat: -33.0472, lng: -71.6127, zoom: 8 },
  "Metropolitana de Santiago": { lat: -33.4489, lng: -70.6693, zoom: 9 },
  "Libertador General Bernardo O'Higgins": { lat: -34.1701, lng: -70.7406, zoom: 8 },
  Maule: { lat: -35.4264, lng: -71.6554, zoom: 8 },
  Ñuble: { lat: -36.6066, lng: -72.1034, zoom: 8 },
  Biobío: { lat: -36.827, lng: -73.0498, zoom: 8 },
  "La Araucanía": { lat: -38.7359, lng: -72.5904, zoom: 8 },
  "Los Ríos": { lat: -39.8142, lng: -73.2459, zoom: 8 },
  "Los Lagos": { lat: -41.4689, lng: -72.9411, zoom: 7 },
  "Aysén del General Carlos Ibáñez del Campo": { lat: -45.5712, lng: -72.0685, zoom: 6 },
  "Magallanes y de la Antártica Chilena": { lat: -53.1638, lng: -70.9171, zoom: 5 },
};

/** Centro de una región canónica, o `null` si no se reconoce. */
export function regionCenter(region: string): RegionCenter | null {
  return REGION_CENTERS[region] ?? null;
}
