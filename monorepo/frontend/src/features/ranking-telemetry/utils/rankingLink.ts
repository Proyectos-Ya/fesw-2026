// Sin "use client": lo importa la página de servidor de la ficha.
import type { CardRanking, InteractionSource, RankingContext } from "../types";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const MAX_POSITION = 100;

/**
 * Enlace a la ficha. Con ranking agrega `?r=<ranking_id>&p=<posición mostrada>`,
 * que es como la ficha sabe de qué lista vino (nunca lo toma de la respuesta de
 * `/recommended`, que la ficha pide solo para encontrar la licitación).
 */
export function tenderDetailHref(tenderId: string, ranking: RankingContext | null): string {
  const base = `/matches/${tenderId}`;
  if (!ranking) return base;
  const params = new URLSearchParams({ r: ranking.rankingId, p: String(ranking.position) });
  return `${base}?${params.toString()}`;
}

/**
 * Lee `r` y `p` de la URL de la ficha. Cualquier cosa que no sea un uuid y un
 * entero de 1 a 100 se descarta: el backend igual valida, pero no hace falta
 * mandarle basura.
 */
export function parseRankingContext(
  r: string | string[] | undefined,
  p: string | string[] | undefined,
): RankingContext | null {
  if (typeof r !== "string" || typeof p !== "string") return null;
  if (!UUID_RE.test(r)) return null;
  if (!/^\d+$/.test(p)) return null;
  const position = Number(p);
  if (position < 1 || position > MAX_POSITION) return null;
  return { rankingId: r, position };
}

/** Contexto de una tarjeta: nulo si la lista no trae `ranking_id` (backend anterior o `track=false`). */
export function cardRanking(
  rankingId: string | null | undefined,
  position: number,
  source: InteractionSource,
): CardRanking | null {
  if (!rankingId) return null;
  return { rankingId, position, source };
}
