import { apiFetch } from "@/features/shared/api/client";
import type { KanbanCard, KanbanColumn } from "../kanbanTypes";

export function fetchColumns(): Promise<KanbanColumn[]> {
  return apiFetch<KanbanColumn[]>("/kanban/columns");
}

export function createColumn(name: string, position?: number): Promise<KanbanColumn> {
  return apiFetch<KanbanColumn>("/kanban/columns", {
    method: "POST",
    body: JSON.stringify({ name, position }),
  });
}

export function updateColumn(id: string, patch: { name?: string; position?: number }): Promise<KanbanColumn> {
  return apiFetch<KanbanColumn>(`/kanban/columns/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export function deleteColumn(id: string): Promise<void> {
  return apiFetch<void>(`/kanban/columns/${id}`, { method: "DELETE" });
}

export function fetchCards(): Promise<KanbanCard[]> {
  return apiFetch<KanbanCard[]>("/kanban/cards");
}

export function addCard(tender_id: string, column_id: string, position?: number): Promise<KanbanCard> {
  return apiFetch<KanbanCard>("/kanban/cards", {
    method: "POST",
    body: JSON.stringify({ tender_id, column_id, position }),
  });
}

export function moveCard(tender_id: string, patch: { column_id?: string; position?: number }): Promise<KanbanCard> {
  return apiFetch<KanbanCard>(`/kanban/cards/${tender_id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export function removeCard(tender_id: string): Promise<void> {
  return apiFetch<void>(`/kanban/cards/${tender_id}`, { method: "DELETE" });
}
