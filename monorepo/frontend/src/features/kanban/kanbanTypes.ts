export interface KanbanColumn {
  id: string;
  name: string;
  position: number;
  color: string;
  card_count: number;
  created_at: string;
}

export interface KanbanCard {
  id: string;
  tender_id: string;
  column_id: string;
  position: number;
  created_at: string;
  updated_at: string;
  board_entered_at: string;
  archived_at: string | null;
  archived_reason: ArchivedReason | null;
}

export type ArchivedReason = "manual" | "auto_3m" | "migration_dedup";

/**
 * Fila del panel de historial (HdU 10, CA4).
 *
 * El backend enriquece la respuesta con el nombre de la columna y los datos
 * de la licitación, para que el panel no tenga que hacer N requests extra.
 */
export interface KanbanArchiveEntry {
  id: string;
  tender_id: string;
  tender_title: string | null;
  tender_external_id: string | null;
  column_id: string;
  column_name: string | null;
  board_entered_at: string;
  archived_at: string;
  archived_reason: ArchivedReason;
}

/**
 * Tipos de evento del historial del tablero del workspace (HU-18).
 *
 * Mantener en sincronía con `KanbanEventType` de
 * `app/domain/entities/kanban_event.py`.
 */
export type KanbanEventType =
  | "column_created"
  | "column_renamed"
  | "column_recolored"
  | "column_reordered"
  | "column_deleted"
  | "card_added"
  | "card_moved"
  | "card_archived"
  | "card_restored"
  | "card_removed";

export type KanbanEntityType = "column" | "card";

/**
 * Entrada del historial del tablero del workspace (HU-18).
 *
 * El backend lo expone en `GET /kanban/events`, paginado por
 * `created_at` descendente. `tender_title` viene desnormalizado para que el
 * panel no necesite joinear con la licitación.
 */
export interface KanbanEvent {
  id: string;
  supplier_id: string;
  /** Autor del evento (quién hizo el cambio). */
  user_id: string;
  event_type: KanbanEventType;
  entity_type: KanbanEntityType | null;
  entity_id: string | null;
  tender_id: string | null;
  tender_title: string | null;
  /**
   * Detalles tipados laxamente del lado del cliente: cada `event_type` guarda
   * un conjunto distinto de claves (p. ej. `from_column`/`to_column` en
   * `card_moved`, `old_name`/`new_name` en `column_renamed`). La UI puede
   * leerlas opcionalmente.
   */
  details: Record<string, unknown>;
  created_at: string;
}
