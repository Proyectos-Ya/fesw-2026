"use client";

/**
 * Panel lateral con el historial unificado del tablero del workspace (HU-18).
 * Muestra todos los eventos (movimientos, archivados, columnas, etc.) en orden
 * cronológico inverso. Para tarjetas archivadas que siguen en archivo ofrece
 * el botón "Restaurar".
 */

import { useEffect, useState } from "react";
import { ApiError } from "@/features/shared/api/client";
import { Icon } from "@/features/shared/components/Icon";
import type { KanbanEvent, KanbanEventType } from "../kanbanTypes";
import * as kanbanService from "../services/kanban.service";

interface Props {
  open: boolean;
  onClose: () => void;
  onRestored?: () => void;
}

function formatDateTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString("es-CL", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

const EVENT_LABELS: Record<KanbanEventType, string> = {
  card_added: "añadió al tablero",
  card_moved: "movió",
  card_archived: "archivó",
  card_restored: "restauró",
  card_removed: "eliminó del tablero",
  column_created: "creó la columna",
  column_renamed: "renombró la columna",
  column_recolored: "cambió color de columna",
  column_reordered: "reorganizó columnas",
  column_deleted: "eliminó la columna",
};

function eventSummary(event: KanbanEvent): string {
  const verb = EVENT_LABELS[event.event_type] ?? event.event_type;
  const d = event.details as Record<string, unknown>;

  if (event.tender_title) {
    if (event.event_type === "card_moved") {
      const from = typeof d.from_column === "string" ? d.from_column : null;
      const to = typeof d.to_column === "string" ? d.to_column : null;
      if (from && to) return `${verb} «${event.tender_title}» de ${from} a ${to}`;
    }
    return `${verb} «${event.tender_title}»`;
  }

  if (event.event_type === "column_renamed") {
    const oldName = typeof d.old_name === "string" ? d.old_name : null;
    const newName = typeof d.new_name === "string" ? d.new_name : null;
    if (oldName && newName) return `renombró «${oldName}» a «${newName}»`;
  }

  if (typeof d.column_name === "string") return `${verb} «${d.column_name}»`;
  return verb;
}

export function HistoryPanel({ open, onClose, onRestored }: Props) {
  const [events, setEvents] = useState<KanbanEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [restoringId, setRestoringId] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    kanbanService
      .listEvents()
      .then((data) => { if (!cancelled) setEvents(data); })
      .catch(() => { if (!cancelled) setError("No se pudo cargar el historial."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [open]);

  const handleRestore = async (cardId: string) => {
    setRestoringId(cardId);
    try {
      await kanbanService.restoreCard(cardId);
      setEvents((prev) =>
        prev.map((e) =>
          e.entity_id === cardId && e.event_type === "card_archived"
            ? { ...e, event_type: "card_restored" as KanbanEventType }
            : e,
        ),
      );
      onRestored?.();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError("Esta tarjeta ya no se puede restaurar.");
      } else {
        setError("No se pudo restaurar la tarjeta.");
      }
    } finally {
      setRestoringId(null);
    }
  };

  return (
    <>
      {open && (
        <button
          type="button"
          onClick={onClose}
          aria-label="Cerrar historial"
          className="fixed inset-0 z-40 bg-black/20"
        />
      )}
      <aside
        className={`fixed top-0 right-0 z-50 h-full w-full max-w-[400px] bg-surface-card shadow-xl border-l border-border-subtle transform transition-transform duration-300 ease-in-out ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
        aria-hidden={!open}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-border-subtle">
          <div className="flex items-center gap-2">
            <Icon name="clock" size={18} />
            <h2 className="font-display text-lg font-bold text-text-strong">
              Historial
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 text-text-subtle hover:text-text-strong rounded-md hover:bg-surface-hover transition-colors"
            aria-label="Cerrar historial"
          >
            <Icon name="x" size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto h-[calc(100%-57px)] px-4 py-3">
          {loading && (
            <p className="text-sm text-text-subtle text-center py-6">
              Cargando historial…
            </p>
          )}
          {error && (
            <p className="text-sm text-danger text-center py-3">{error}</p>
          )}
          {!loading && !error && events.length === 0 && (
            <p className="text-sm text-text-subtle text-center py-6">
              Todavía no hay actividad registrada.
            </p>
          )}
          <ul className="space-y-0">
            {events.map((event) => (
              <li
                key={event.id}
                className="flex items-start gap-3 py-3 border-b border-border-subtle last:border-0"
              >
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-text-strong leading-snug">
                    <span className="font-bold">
                      {event.user_name ?? "Alguien"}
                    </span>{" "}
                    {eventSummary(event)}
                  </p>
                  <p className="text-xs text-text-subtle mt-0.5">
                    {formatDateTime(event.created_at)}
                  </p>
                </div>
                {event.event_type === "card_archived" && event.entity_id && (
                  <button
                    type="button"
                    onClick={() => void handleRestore(event.entity_id!)}
                    disabled={restoringId === event.entity_id}
                    className="text-xs font-semibold text-primary hover:text-primary-hover disabled:opacity-50 whitespace-nowrap mt-0.5"
                  >
                    {restoringId === event.entity_id ? "Restaurando…" : "Restaurar"}
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </>
  );
}
