import { apiFetch } from "@/features/shared/api/client";
import type {
  InteractionKind,
  InteractionSource,
  RankingContext,
  TenderInteractionAck,
  TenderInteractionBody,
} from "../types";

export function buildInteractionBody(
  kind: InteractionKind,
  source: InteractionSource,
  ranking: RankingContext | null,
): TenderInteractionBody {
  // Sin ranking no viaja la posición: una posición sin su lista no se puede atribuir a nada.
  return ranking
    ? { kind, source, ranking_id: ranking.rankingId, position: ranking.position }
    : { kind, source };
}

/**
 * Backend route: POST /tenders/{tender_id}/interactions
 *
 * Fire-and-forget: la telemetría nunca rompe ni demora la interfaz, y un 404 o
 * 405 de un backend anterior se silencia.
 */
export function reportTenderInteraction(
  tenderId: string,
  kind: InteractionKind,
  source: InteractionSource,
  ranking: RankingContext | null,
): void {
  try {
    void apiFetch<TenderInteractionAck>(`/tenders/${encodeURIComponent(tenderId)}/interactions`, {
      method: "POST",
      body: JSON.stringify(buildInteractionBody(kind, source, ranking)),
      keepalive: true, // sobrevive a que el usuario se vaya de la página
    }).catch(() => undefined);
  } catch {
    // apiFetch no lanza en forma sincrónica, pero un clic no puede fallar por telemetría.
  }
}
