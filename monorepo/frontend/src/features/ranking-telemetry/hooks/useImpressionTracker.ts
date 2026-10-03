import { useCallback, useEffect, useState } from "react";
import { reportTenderInteraction } from "../services/rankingTelemetryService";
import type { InteractionSource, RankingContext } from "../types";

/**
 * Mitad de la tarjeta a la vista durante 1 s: el criterio de impresión vista de la IAB.
 * El segundo también da tiempo a que el backend termine de escribir el ranking.
 */
export const IMPRESSION_VISIBLE_RATIO = 0.5;
export const IMPRESSION_MIN_VISIBLE_MS = 1000;

// A nivel de módulo y no del componente: una tarjeta se desmonta al cambiar de página o de
// filtro y al volver no debe contar de nuevo. Clave ranking+licitación: otra lista sí cuenta.
const reported = new Set<string>();

/** Solo para tests. */
export function resetReportedImpressions(): void {
  reported.clear();
}

/** Informa la impresión una sola vez por (ranking, licitación) en toda la SPA. */
export function reportImpressionOnce(
  tenderId: string,
  ranking: RankingContext,
  source: InteractionSource,
): void {
  const key = `${ranking.rankingId}:${tenderId}`;
  if (reported.has(key)) return;
  reported.add(key);
  reportTenderInteraction(tenderId, "impresion", source, ranking);
}

export interface ImpressionTarget {
  tenderId: string;
  ranking: RankingContext;
  source: InteractionSource;
}

/**
 * Ref para el elemento de una tarjeta: informa la impresión cuando estuvo visible
 * al menos la mitad durante 1 s. Con `target` nulo (sin ranking) no hace nada.
 */
export function useImpressionRef(
  target: ImpressionTarget | null,
): (node: HTMLElement | null) => void {
  const [node, setNode] = useState<HTMLElement | null>(null);
  const tenderId = target?.tenderId ?? null;
  const rankingId = target?.ranking.rankingId ?? null;
  const position = target?.ranking.position ?? null;
  const source = target?.source ?? null;

  useEffect(() => {
    if (!node || tenderId === null || rankingId === null || position === null || source === null) {
      return;
    }
    // jsdom y navegadores viejos no lo tienen: sin observador no hay telemetría, pero tampoco error.
    if (typeof IntersectionObserver === "undefined") return;
    if (reported.has(`${rankingId}:${tenderId}`)) return;

    const id: string = tenderId;
    const ctx: RankingContext = { rankingId, position };
    const src: InteractionSource = source;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const clear = () => {
      if (timer !== null) {
        clearTimeout(timer);
        timer = null;
      }
    };

    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[entries.length - 1];
        if (!entry) return;
        // Margen de 0,01: en el cruce exacto el navegador puede informar 0,4999.
        const visible =
          entry.isIntersecting && entry.intersectionRatio >= IMPRESSION_VISIBLE_RATIO - 0.01;
        if (!visible) {
          clear();
          return;
        }
        if (timer !== null) return;
        timer = setTimeout(() => {
          timer = null;
          reportImpressionOnce(id, ctx, src);
          observer.disconnect();
        }, IMPRESSION_MIN_VISIBLE_MS);
      },
      { threshold: [0, IMPRESSION_VISIBLE_RATIO] },
    );
    observer.observe(node);

    return () => {
      clear();
      observer.disconnect();
    };
  }, [node, tenderId, rankingId, position, source]);

  // Sin objetivo (búsqueda, guardadas) el ref no toca el estado: así la tarjeta no
  // suma un render extra por una telemetría que no va a hacer nada.
  const enabled = target !== null;
  return useCallback(
    (el: HTMLElement | null) => {
      if (enabled) setNode(el);
    },
    [enabled],
  );
}
