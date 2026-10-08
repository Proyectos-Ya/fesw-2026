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

export type ArchivedReason = "manual" | "auto_3m";

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
