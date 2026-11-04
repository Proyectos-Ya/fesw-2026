"use client";

/**
 * Panel lateral derecho con dos pestañas:
 * - Archivadas (HdU 10, CA4): tarjetas archivadas, restaurables manualmente.
 * - Actividad (HU-18): historial de eventos del tablero compartido del workspace.
 */

import { useEffect, useState } from "react";
import { ApiError } from "@/features/shared/api/client";
import { Icon } from "@/features/shared/components/Icon";
import type { KanbanArchiveEntry, KanbanEvent, KanbanEventType } from "../kanbanTypes";
import * as kanbanService from "../services/kanban.service";

interface Props {
  open: boolean;
  onClose: () => void;
  onRestored?: () => void;
}

type PanelTab = "archivadas" | "actividad";

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("es-CL", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return iso;
  }
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
  const [tab, setTab] = useState<PanelTab>("archivadas");

  // --- Archivadas state ---
  const [entries, setEntries] = useState<KanbanArchiveEntry[]>([]);
  const [loadingArchive, setLoadingArchive] = useState(false);
  const [errorArchive, setErrorArchive] = useState<string | null>(null);
  const [restoringId, setRestoringId] = useState<string | null>(null);

  // --- Actividad state ---
  const [events, setEvents] = useState<KanbanEvent[]>([]);
  const [loadingEvents, setLoadingEvents] = useState(false);
  const [errorEvents, setErrorEvents] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    if (tab === "archivadas") {
      let cancelled = false;
      setLoadingArchive(true);
      setErrorArchive(null);
      kanbanService
        .listArchive()
        .then((data) => { if (!cancelled) setEntries(data); })
        .catch(() => { if (!cancelled) setErrorArchive("No se pudo cargar el historial."); })
        .finally(() => { if (!cancelled) setLoadingArchive(false); });
      return () => { cancelled = true; };
    } else {
      let cancelled = false;
      setLoadingEvents(true);
      setErrorEvents(null);
      kanbanService
        .listEvents()
        .then((data) => { if (!cancelled) setEvents(data); })
        .catch(() => { if (!cancelled) setErrorEvents("No se pudo cargar la actividad."); })
        .finally(() => { if (!cancelled) setLoadingEvents(false); });
      return () => { cancelled = true; };
    }
  }, [open, tab]);

  const handleRestore = async (entry: KanbanArchiveEntry) => {
    setRestoringId(entry.id);
    try {
      await kanbanService.restoreCard(entry.id);
      setEntries((prev) => prev.filter((e) => e.id !== entry.id));
      onRestored?.();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setErrorArchive("Esta tarjeta ya no se puede restaurar.");
      } else {
        setErrorArchive("No se pudo restaurar la tarjeta.");
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

        {/* Tabs */}
        <div
          role="tablist"
          className="flex border-b border-border-subtle px-4"
        >
          {(["archivadas", "actividad"] as PanelTab[]).map((t) => (
            <button
              key={t}
              type="button"
              role="tab"
              aria-selected={tab === t}
              onClick={() => setTab(t)}
              className={`py-2.5 px-3 text-sm font-semibold border-b-2 transition-colors capitalize ${
                tab === t
                  ? "border-primary text-primary"
                  : "border-transparent text-text-muted hover:text-text-strong"
              }`}
            >
              {t === "archivadas" ? "Archivadas" : "Actividad"}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto h-[calc(100%-105px)] px-4 py-3 space-y-2">
          {/* Archivadas tab */}
          {tab === "archivadas" && (
            <>
              {loadingArchive && (
                <p className="text-sm text-text-subtle text-center py-6">Cargando…</p>
              )}
              {errorArchive && (
                <p className="text-sm text-danger text-center py-3">{errorArchive}</p>
              )}
              {!loadingArchive && !errorArchive && entries.length === 0 && (
                <p className="text-sm text-text-subtle text-center py-6">
                  Todavía no hay tarjetas archivadas.
                </p>
              )}
              {entries.map((entry) => (
                <article
                  key={entry.id}
                  className="bg-bg-sunken border border-border-subtle rounded-lg p-3 flex flex-col gap-1.5"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-[0.6875rem] text-text-subtle font-mono truncate">
                        {entry.tender_external_id ?? entry.tender_id}
                      </p>
                      <p className="text-sm font-semibold text-text-strong line-clamp-2 mt-0.5">
                        {entry.tender_title ?? "Licitación sin título"}
                      </p>
                    </div>
                    {entry.archived_reason === "manual" && (
                      <button
                        type="button"
                        onClick={() => void handleRestore(entry)}
                        disabled={restoringId === entry.id}
                        className="text-xs font-semibold text-primary hover:text-primary-hover disabled:opacity-50 whitespace-nowrap"
                      >
                        {restoringId === entry.id ? "Restaurando…" : "Restaurar"}
                      </button>
                    )}
                  </div>
                  <dl className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-xs text-text-muted">
                    <dt className="text-text-subtle">Columna</dt>
                    <dd className="text-text-strong truncate">
                      {entry.column_name ?? "—"}
                    </dd>
                    <dt className="text-text-subtle">Entró</dt>
                    <dd>{formatDate(entry.board_entered_at)}</dd>
                    <dt className="text-text-subtle">Archivada</dt>
                    <dd>{formatDate(entry.archived_at)}</dd>
                    <dt className="text-text-subtle">Razón</dt>
                    <dd>
                      {entry.archived_reason === "manual"
                        ? "Manual"
                        : "Inactividad (+90 días)"}
                    </dd>
                  </dl>
                </article>
              ))}
            </>
          )}

          {/* Actividad tab */}
          {tab === "actividad" && (
            <>
              {loadingEvents && (
                <p className="text-sm text-text-subtle text-center py-6">Cargando…</p>
              )}
              {errorEvents && (
                <p className="text-sm text-danger text-center py-3">{errorEvents}</p>
              )}
              {!loadingEvents && !errorEvents && events.length === 0 && (
                <p className="text-sm text-text-subtle text-center py-6">
                  Todavía no hay actividad registrada.
                </p>
              )}
              {events.map((event) => (
                <div
                  key={event.id}
                  className="flex items-start gap-2.5 py-2 border-b border-border-subtle last:border-0"
                >
                  <div className="mt-0.5 flex-none size-6 rounded-full bg-primary-soft flex items-center justify-center">
                    <Icon name="activity" size={12} className="text-primary" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-text-strong leading-snug">
                      {eventSummary(event)}
                    </p>
                    <p className="text-xs text-text-subtle mt-0.5">
                      {formatDateTime(event.created_at)}
                    </p>
                  </div>
                </div>
              ))}
            </>
          )}
        </div>
      </aside>
    </>
  );
}
