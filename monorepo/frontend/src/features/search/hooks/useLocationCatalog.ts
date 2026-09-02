"use client";

import { useEffect, useState } from "react";
import { getLocationCatalog } from "../services/locationCatalogService";
import type { CommuneOption, ProvinceOption } from "../types";

export interface UseLocationCatalogResult {
  provinces: ProvinceOption[];
  communes: CommuneOption[];
  isLoading: boolean;
  error: string | null;
}

export function useLocationCatalog(): UseLocationCatalogResult {
  const [provinces, setProvinces] = useState<ProvinceOption[]>([]);
  const [communes, setCommunes] = useState<CommuneOption[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    getLocationCatalog()
      .then((data) => {
        if (!cancelled) {
          setProvinces(data.provinces);
          setCommunes(data.communes);
          setIsLoading(false);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          const message =
            err instanceof Error
              ? err.message
              : "No se pudo cargar el catálogo de ubicaciones.";
          setError(message);
          setIsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return {
    provinces,
    communes,
    isLoading,
    error,
  };
}
