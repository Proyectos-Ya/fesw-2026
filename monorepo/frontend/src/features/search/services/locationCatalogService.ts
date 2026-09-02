import { apiFetch } from "@/features/shared/api/client";
import type { LocationCatalogResponse } from "../types";

let catalogCache: LocationCatalogResponse | null = null;
let catalogPromise: Promise<LocationCatalogResponse> | null = null;

export const LOCATIONS_CATALOG_STORAGE_KEY = "proyectosya_locations_catalog";

/**
 * Obtiene el catálogo de provincias y comunas de Chile (GET /catalogs/locations).
 * Aplica caché en memoria a nivel de módulo y persistencia en sessionStorage
 * para solicitarlo únicamente una vez por sesión.
 */
export async function getLocationCatalog(): Promise<LocationCatalogResponse> {
  if (catalogCache) {
    return catalogCache;
  }

  if (typeof window !== "undefined") {
    try {
      const stored = window.sessionStorage.getItem(LOCATIONS_CATALOG_STORAGE_KEY);
      if (stored) {
        catalogCache = JSON.parse(stored) as LocationCatalogResponse;
        return catalogCache;
      }
    } catch {
      // Ignorar fallos de acceso o parseo en sessionStorage
    }
  }

  if (!catalogPromise) {
    catalogPromise = apiFetch<LocationCatalogResponse>("/catalogs/locations")
      .then((data) => {
        catalogCache = data;
        if (typeof window !== "undefined") {
          try {
            window.sessionStorage.setItem(
              LOCATIONS_CATALOG_STORAGE_KEY,
              JSON.stringify(data),
            );
          } catch {
            // Ignorar fallos de escritura en sessionStorage
          }
        }
        return data;
      })
      .catch((err: unknown) => {
        catalogPromise = null;
        throw err;
      });
  }

  return catalogPromise;
}

/**
 * Limpia la caché en memoria y la clave correspondiente en sessionStorage.
 */
export function clearLocationCatalogCache(): void {
  catalogCache = null;
  catalogPromise = null;
  if (typeof window !== "undefined") {
    try {
      window.sessionStorage.removeItem(LOCATIONS_CATALOG_STORAGE_KEY);
    } catch {
      // Ignorar
    }
  }
}
