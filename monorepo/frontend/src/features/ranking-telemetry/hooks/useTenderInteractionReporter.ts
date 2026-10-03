import { useCallback, useRef } from "react";
import { reportTenderInteraction } from "../services/rankingTelemetryService";
import type { InteractionKind, InteractionSource, RankingContext } from "../types";

/**
 * Para la ficha: cada tipo se informa una vez por licitación y ranking mientras está
 * montada. El backend también deduplica lo atribuido; esto evita ráfagas de lo que no lo está.
 */
export function useTenderInteractionReporter(
  tenderId: string,
  ranking: RankingContext | null,
  source: InteractionSource = "detalle",
): (kind: InteractionKind) => void {
  const rankingId = ranking?.rankingId ?? null;
  const position = ranking?.position ?? null;
  const sent = useRef<Set<string>>(new Set());

  return useCallback(
    (kind: InteractionKind) => {
      const key = `${tenderId}:${rankingId ?? "-"}:${kind}`;
      if (sent.current.has(key)) return;
      sent.current.add(key);
      reportTenderInteraction(
        tenderId,
        kind,
        source,
        rankingId !== null && position !== null ? { rankingId, position } : null,
      );
    },
    [tenderId, rankingId, position, source],
  );
}
