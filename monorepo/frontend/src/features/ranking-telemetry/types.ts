/** Debe calzar con `InteractionKind` del backend (app/domain/entities/ranking_telemetry.py). */
export type InteractionKind =
  | "impresion"
  | "detalle"
  | "guardar"
  | "ficha_mp"
  | "anexo"
  | "asistente"
  | "analisis"
  | "cotizacion";

/** Superficie donde ocurre. El backend acepta además búsqueda, guardadas y notificación. */
export type InteractionSource = "inicio" | "matches" | "detalle";

/** Lista servida (`ranking_id`) y posición MOSTRADA, 1..N, tras filtros y paginación. */
export interface RankingContext {
  rankingId: string;
  position: number;
}

/** Lo que una tarjeta necesita para reportarse: el ranking y desde dónde se muestra. */
export interface CardRanking extends RankingContext {
  source: InteractionSource;
}

export interface TenderInteractionBody {
  kind: InteractionKind;
  source: InteractionSource;
  ranking_id?: string;
  position?: number;
}

export interface TenderInteractionAck {
  recorded: boolean;
  attributed: boolean;
}
