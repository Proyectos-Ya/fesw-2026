"use client";

/**
 * Panel lateral derecho con el historial de tarjetas archivadas (HdU 10, CA4).
 *
 * Monta un drawer que entra con slide-in desde la derecha. Carga el historial
 * cuando se abre (no se queda escuchando mientras está cerrado). Cada entrada
 * muestra la licitación, cuándo entró y salió del tablero, en qué columna
 * estaba y la razón; el botón "Restaurar" solo aparece para las archivadas
 * manualmente, consistente con la regla de negocio del backend.
 */

import { useEffect, useState } from "react";
import { ApiError } from "@/features/shared/api/client";
import { Icon } from "@/features/shared/components/Icon";
import type { KanbanArchiveEntry } from "../kanbanTypes";
import * as kanbanService from "../services/kanban.service";

interface Props {
  open: boolean;
  onClose: () => void;
  onRestored?: () => void;
}

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

export function HistoryPanel({ open, onClose, onRestored }: Props) {
  const [entries, setEntries] = useState<KanbanArchiveEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [restoringId, setRestoringId] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    kanbanService
      .listArchive()
      .then((data) => {
        if (!cancelled) setEntries(data);
      })
      .catch(() => {
        if (!cancelled) setError("No se pudo cargar el historial.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open]);

  const handleRestore = async (entry: KanbanArchiveEntry) => {
    setRestoringId(entry.id);
    try {
      await kanbanService.restoreCard(entry.id);
      setEntries((prev) => prev.filter((e) => e.id !== entry.id));
      onRestored?.();
    } catch (err) {
      // Si el backend cambió el estado y ya no se puede restaurar, mostramos
      // un mensaje; de lo contrario, dejamos la entrada para reintentar.
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
        className={`fixed top-0 right-0 z-50 h-full w-[400px] bg-surface-card shadow-xl border-l border-border-subtle transform transition-transform duration-300 ease-in-out ${
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
            className="p-1 text-text-subtle hover:text-text-strong rounded-md hover:bg-warm-100 transition-colors"
            aria-label="Cerrar historial"
          >
            <Icon name="x" size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto h-[calc(100%-57px)] px-4 py-3 space-y-2">
          {loading && (
            <p className="text-sm text-text-subtle text-center py-6">
              Cargando historial…
            </p>
          )}
          {error && (
            <p className="text-sm text-danger text-center py-3">{error}</p>
          )}
          {!loading && !error && entries.length === 0 && (
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
                  <p className="text-[11px] text-text-subtle font-mono truncate">
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
        </div>
      </aside>
    </>
  );
}
