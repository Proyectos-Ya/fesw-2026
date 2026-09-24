export interface KanbanColumn {
  id: string;
  name: string;
  position: number;
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
}
