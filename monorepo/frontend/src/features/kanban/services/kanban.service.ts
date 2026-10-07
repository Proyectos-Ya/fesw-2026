import { apiFetch } from "@/features/shared/api/client";
import type { KanbanArchiveEntry, KanbanCard, KanbanColumn } from "../kanbanTypes";

export function fetchColumns(): Promise<KanbanColumn[]> {
  return apiFetch<KanbanColumn[]>("/kanban/columns");
}

export function createColumn(name: string, position?: number): Promise<KanbanColumn> {
  return apiFetch<KanbanColumn>("/kanban/columns", {
    method: "POST",
    body: JSON.stringify({ name, position }),
  });
}

export function updateColumn(id: string, patch: { name?: string; position?: number; color?: string }): Promise<KanbanColumn> {
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

/**
 * Archivado manual de una tarjeta (HdU 10, CA4). La tarjeta deja de aparecer
 * en el tablero activo y pasa al historial, de donde se puede restaurar.
 */
export function archiveCard(card_id: string): Promise<KanbanCard> {
  return apiFetch<KanbanCard>(`/kanban/cards/${card_id}/archive`, {
    method: "POST",
  });
}

/** Historial de tarjetas archivadas del usuario (más reciente primero). */
export function listArchive(): Promise<KanbanArchiveEntry[]> {
  return apiFetch<KanbanArchiveEntry[]>("/kanban/archive");
}

/**
 * Restaura al tablero una tarjeta archivada manualmente. El backend responde
 * 409 si fue auto-archivada (`auto_3m`): el panel debería ocultar el botón
 * en esos casos, pero manejamos el error por si acaso.
 */
export function restoreCard(card_id: string): Promise<KanbanCard> {
  return apiFetch<KanbanCard>(`/kanban/archive/${card_id}/restore`, {
    method: "POST",
  });
}
