"use client";

import { useCallback, useEffect, useState } from "react";
import { getTendersMap } from "../services/tenderMapService";
import type { TenderMapResult } from "../types";

export interface UseTenderMap {
  data: TenderMapResult | null;
  loading: boolean;
  /** La vista muestra "No se pudo cargar el mapa"; el detalle técnico no le sirve al usuario. */
  error: boolean;
  retry: () => void;
}

interface Respuesta {
  /** De qué pedido es: zona y número de reintento. */
  clave: string;
  data: TenderMapResult | null;
  error: boolean;
}

/** Marcadores de la zona elegida. Sin zona no pide nada (HU-22, #314). */
export function useTenderMap(region: string | null): UseTenderMap {
  const [retryNonce, setRetryNonce] = useState(0);
  const [respuesta, setRespuesta] = useState<Respuesta | null>(null);
  const clave = region === null ? null : `${region}#${retryNonce}`;

  useEffect(() => {
    if (region === null || clave === null) return;
    // Una respuesta que llega después de cambiar de zona es de otra zona.
    let cancelled = false;
    getTendersMap(region)
      .then((data) => {
        if (!cancelled) setRespuesta({ clave, data, error: false });
      })
      .catch(() => {
        if (!cancelled) setRespuesta({ clave, data: null, error: true });
      });
    return () => {
      cancelled = true;
    };
  }, [region, clave]);

  const retry = useCallback(() => setRetryNonce((n) => n + 1), []);

  // Lo que hay guardado solo vale si es del pedido actual; si no, se está cargando.
  const vigente = respuesta !== null && respuesta.clave === clave ? respuesta : null;
  return {
    data: vigente?.data ?? null,
    loading: clave !== null && vigente === null,
    error: vigente?.error ?? false,
    retry,
  };
}
