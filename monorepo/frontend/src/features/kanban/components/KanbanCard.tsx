"use client";

import React from "react";
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

export function KanbanCard({ card, tender, onRemove }: Props) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: card.id });

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
            <button
              onClick={(e) => { e.stopPropagation(); onRemove(card.tender_id); }}
              className="flex-none p-0.5 text-text-subtle opacity-0 group-hover:opacity-100 hover:text-danger transition-all"
              aria-label="Quitar del tablero"
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
    </div>
  );
}
