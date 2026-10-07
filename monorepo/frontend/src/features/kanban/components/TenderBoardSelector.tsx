"use client";

/**
 * Selector de categoría del tablero Kanban en la vista de detalle de una
 * licitación (HdU 10, CA3).
 *
 * Resumen de los cuatro estados:
 *  - loading: mientras `useKanban` carga columnas y tarjetas.
 *  - sin columnas: CTA "Crear tablero" (llama `onNavigateToBoard` o navega a
 *    `/tablero` por defecto).
 *  - no en tablero: dropdown "Agregar al tablero" → al elegir, `addCard`.
 *  - en tablero: trigger pre-selecciona la columna actual; cambiar llama
 *    `moveCard` y la opción "Quitar del tablero" llama `archiveCard` tras
 *    confirmación.
 *
 * El contrato con el hook `useKanban` es intencional: `addCard` y `moveCard`
 * identifican la tarjeta por `tender_id`; `archiveCard` por `card.id` (id
 * interno del backend), que mapeamos acá a partir de `cards`.
 */

import { useMemo, useRef, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Icon } from "@/features/shared/components/Icon";
import { getTenderDetail } from "@/features/matches/services/tenderService";
import type { Tender } from "@/features/matches/tenderTypes";
import { useKanban } from "../hooks/useKanban";
import type { KanbanCard, KanbanColumn } from "../kanbanTypes";

interface Props {
  tenderId: string;
  onNavigateToBoard?: () => void;
}

export function TenderBoardSelector({ tenderId, onNavigateToBoard }: Props) {
  const router = useRouter();
  const { columns, cards, loading, addCard, moveCard, archiveCard } = useKanban();

  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Tarjeta de este tender dentro del tablero activo (si existe).
  const currentCard: KanbanCard | undefined = useMemo(
    () => cards.find((c) => c.tender_id === tenderId),
    [cards, tenderId],
  );
  const currentColumn: KanbanColumn | undefined = useMemo(
    () =>
      currentCard
        ? columns.find((col) => col.id === currentCard.column_id)
        : undefined,
    [columns, currentCard],
  );

  // Cerrar al clickear afuera del contenedor.
  useEffect(() => {
    if (!open) return;
    const handler = (event: MouseEvent) => {
      if (!containerRef.current) return;
      if (!containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const handleCreateBoard = () => {
    if (onNavigateToBoard) onNavigateToBoard();
    else router.push("/tablero");
  };

  const handlePickColumn = async (columnId: string) => {
    setOpen(false);
    setError(null);
    setBusy(true);
    try {
      if (currentCard) {
        if (currentCard.column_id === columnId) return;
        const cardsInTarget = cards.filter((c) => c.column_id === columnId);
        await moveCard(tenderId, columnId, cardsInTarget.length);
      } else {
        // Para `addCard` necesitamos un `Tender`. Lo buscamos si aún no está
        // en el mapa de `useKanban`; es un fetch barato que respeta el
        // contrato del hook (que lo guarda en su estado interno).
        let tender: Tender | undefined;
        try {
          const detail = await getTenderDetail(tenderId);
          tender = detail.tender;
        } catch {
          setError("No se pudo cargar la licitación. Intenta de nuevo.");
          return;
        }
        await addCard(tenderId, columnId, tender);
      }
    } catch {
      setError("No se pudo actualizar el tablero. Intenta de nuevo.");
    } finally {
      setBusy(false);
    }
  };

  const handleRemove = async () => {
    if (!currentCard) return;
    const ok =
      typeof window !== "undefined"
        ? window.confirm(
            "¿Quitar esta licitación del tablero? Pasará al historial y podrás restaurarla desde allí.",
          )
        : true;
    if (!ok) return;
    setOpen(false);
    setError(null);
    setBusy(true);
    try {
      await archiveCard(currentCard.id);
    } catch {
      setError("No se pudo quitar la tarjeta. Intenta de nuevo.");
    } finally {
      setBusy(false);
    }
  };

  // --- Estado 1: loading ---------------------------------------------------
  if (loading) {
    return (
      <div
        data-testid="tender-board-selector-loading"
        className="inline-flex items-center gap-2 rounded-md border border-border-subtle bg-surface-card px-3 py-2 text-sm text-text-muted"
      >
        <Icon name="loader-circle" size={14} className="animate-spin" />
        <span>Cargando tablero…</span>
      </div>
    );
  }

  // --- Estado 2: sin columnas ---------------------------------------------
  if (columns.length === 0) {
    return (
      <button
        type="button"
        onClick={handleCreateBoard}
        className="inline-flex items-center gap-2 rounded-md border border-border-strong bg-white px-3 py-2 text-sm font-semibold text-text-strong transition-colors hover:bg-slate-50"
      >
        <Icon name="plus" size={14} />
        <span>Crear tablero</span>
      </button>
    );
  }

  // --- Estados 3 y 4: dropdown --------------------------------------------
  const triggerLabel = currentColumn ? currentColumn.name : "Agregar al tablero";

  return (
    <div ref={containerRef} className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        disabled={busy}
        aria-haspopup="menu"
        aria-expanded={open}
        className={`inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-semibold transition-colors ${
          currentColumn
            ? "border-border-strong bg-primary-soft text-primary hover:bg-teal-100"
            : "border-border-strong bg-white text-text-strong hover:bg-slate-50"
        } disabled:cursor-not-allowed disabled:opacity-60`}
      >
        {currentColumn ? (
          <span
            className="inline-block h-2.5 w-2.5 rounded-full"
            style={{ backgroundColor: currentColumn.color }}
            aria-hidden="true"
          />
        ) : (
          <Icon name="plus" size={14} />
        )}
        <span>{triggerLabel}</span>
        <Icon name="chevron-down" size={14} />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 z-20 mt-1 w-60 overflow-hidden rounded-md border border-border-subtle bg-surface-card shadow-md"
        >
          <div className="max-h-72 overflow-y-auto py-1">
            {columns.map((col) => {
              const isCurrent = currentColumn?.id === col.id;
              return (
                <button
                  key={col.id}
                  type="button"
                  role="menuitem"
                  onClick={() => void handlePickColumn(col.id)}
                  className={`flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm transition-colors hover:bg-warm-100 ${
                    isCurrent ? "font-semibold text-primary" : "text-text-body"
                  }`}
                >
                  <span className="inline-flex items-center gap-2">
                    <span
                      className="inline-block h-2.5 w-2.5 rounded-full"
                      style={{ backgroundColor: col.color }}
                      aria-hidden="true"
                    />
                    <span>{col.name}</span>
                  </span>
                  {isCurrent && <Icon name="check" size={14} />}
                </button>
              );
            })}
          </div>

          {currentCard && (
            <div className="border-t border-border-subtle py-1">
              <button
                type="button"
                role="menuitem"
                onClick={() => void handleRemove()}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-danger transition-colors hover:bg-danger-soft/40"
              >
                <Icon name="trash-2" size={14} />
                <span>Quitar del tablero</span>
              </button>
            </div>
          )}
        </div>
      )}

      {error && (
        <div
          role="alert"
          className="absolute right-0 mt-1 w-60 rounded-md border border-danger/20 bg-danger-soft/30 px-3 py-2 text-xs text-danger"
        >
          {error}
        </div>
      )}
    </div>
  );
}
