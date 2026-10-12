"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type { Tender } from "@/features/matches/tenderTypes";
import {
  daysUntilClosing,
  formatCLP,
  formatClosingDate,
} from "@/features/matches/utils/format";
import { Badge } from "@/features/shared/components/Badge";
import { Icon } from "@/features/shared/components/Icon";
import type { KanbanCard as KanbanCardType } from "../kanbanTypes";

interface Props {
  card: KanbanCardType;
  tender: Tender | undefined;
  onRemove: (tender_id: string) => void;
  onArchive?: (card_id: string) => void;
}

function DeadlineBadge({ closingAt }: { closingAt: string }) {
  const closing = daysUntilClosing(closingAt);
  if (closing.tone === "expired") {
    return <Badge tone="neutral">{closing.label}</Badge>;
  }
  if (closing.days <= 5) {
    return (
      <Badge tone="warning" dot>
        {closing.label}
      </Badge>
    );
  }
  return (
    <Badge tone="neutral" iconLeft={<Icon name="calendar" size={10} />}>
      Cierra {formatClosingDate(closingAt)}
    </Badge>
  );
}

export function KanbanCard({ card, tender, onRemove, onArchive }: Props) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: card.id });
  const [menuOpen, setMenuOpen] = useState(false);
  const [confirmArchive, setConfirmArchive] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Click fuera cierra el menú contextual. Lo manejamos manualmente en vez de
  // montar un portal: el menú es local y pequeño, no vale la pena.
  useEffect(() => {
    if (!menuOpen) return;
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [menuOpen]);

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className="bg-surface-card border border-border-subtle rounded-lg py-2.5 px-2 flex flex-col gap-1.5 group shadow-xs hover:border-border-default hover:shadow-md transition-all duration-200 cursor-grab active:cursor-grabbing"
    >
      {tender ? (
        <>
          <div className="flex items-center gap-1 min-w-0">
            <p className="text-[11px] text-text-subtle font-mono truncate leading-none flex-1">
              {tender.code}
            </p>
            {onArchive && (
              <div ref={menuRef} className="relative flex-none">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setMenuOpen((v) => !v);
                  }}
                  onPointerDown={(e) => e.stopPropagation()}
                  className="p-0.5 text-text-subtle opacity-0 group-hover:opacity-100 hover:text-text-strong transition-all"
                  aria-label="Más acciones"
                  type="button"
                >
                  <Icon name="more-vertical" size={13} />
                </button>
                {menuOpen && (
                  <div
                    className="absolute right-0 top-5 z-10 w-36 bg-surface-card border border-border-subtle rounded-md shadow-md py-1 text-left"
                    onPointerDown={(e) => e.stopPropagation()}
                  >
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setMenuOpen(false);
                        setConfirmArchive(true);
                      }}
                      className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-text-body hover:bg-warm-100"
                    >
                      <Icon name="archive" size={12} />
                      Archivar
                    </button>
                  </div>
                )}
              </div>
            )}
            <button
              onClick={(e) => {
                e.stopPropagation();
                if (onArchive) {
                  setConfirmArchive(true);
                } else {
                  onRemove(card.tender_id);
                }
              }}
              onPointerDown={(e) => e.stopPropagation()}
              className="flex-none p-0.5 text-text-subtle opacity-0 group-hover:opacity-100 hover:text-danger transition-all"
              aria-label={onArchive ? "Archivar tarjeta" : "Quitar del tablero"}
              type="button"
            >
              <Icon name="x" size={13} />
            </button>
          </div>
          <Link href={`/matches/${card.tender_id}`} className="block" onClick={(e) => e.stopPropagation()}>
            <p className="text-sm font-semibold text-text-strong leading-5 line-clamp-2 hover:text-primary transition-colors">
              {tender.name}
            </p>
          </Link>
          {(tender.buyer_name ?? tender.buyer_unit) && (
            <p className="text-xs text-text-muted truncate">
              {tender.buyer_name ?? tender.buyer_unit}
              {tender.region ? ` · ${tender.region}` : ""}
            </p>
          )}
          <DeadlineBadge closingAt={tender.closing_at} />
          {tender.available_amount_clp != null && (
            <div className="mt-0.5 pt-2 border-t border-border-subtle flex items-center justify-between">
              <span className="font-mono text-[12px] font-semibold text-text-strong">
                {formatCLP(tender.available_amount_clp)}
              </span>
              <span className="text-xs text-text-muted">Sin asignar</span>
            </div>
          )}
        </>
      ) : (
        <p className="text-xs text-text-subtle font-mono truncate">
          {card.tender_id}
        </p>
      )}

      {confirmArchive && onArchive && (
        <div
          className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center"
          onClick={(e) => { e.stopPropagation(); setConfirmArchive(false); }}
          onPointerDown={(e) => e.stopPropagation()}
        >
          <div
            className="bg-surface-card rounded-lg shadow-lg border border-border-subtle p-5 max-w-sm w-[90%]"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="font-display text-base font-bold text-text-strong mb-2">
              Archivar tarjeta
            </h3>
            <p className="text-sm text-text-body mb-4">
              La tarjeta pasará al historial. Podrás restaurarla desde el panel
              lateral mientras la archives tú mismo.
            </p>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setConfirmArchive(false)}
                className="px-3 py-1.5 text-sm text-text-subtle hover:text-text-strong rounded-md hover:bg-warm-100"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={() => {
                  onArchive(card.id);
                  setConfirmArchive(false);
                }}
                className="px-3 py-1.5 text-sm font-semibold bg-primary text-on-primary rounded-md hover:bg-primary-hover"
              >
                Archivar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
