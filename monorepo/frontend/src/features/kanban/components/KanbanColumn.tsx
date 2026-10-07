"use client";

import React, { useEffect, useRef, useState } from "react";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { useDroppable } from "@dnd-kit/core";
import type { Tender } from "@/features/matches/tenderTypes";
import { Icon } from "@/features/shared/components/Icon";
import type { KanbanCard as KanbanCardType, KanbanColumn as KanbanColumnType } from "../kanbanTypes";
import { AddTenderModal } from "./AddTenderModal";
import { KanbanCard } from "./KanbanCard";
import { KanbanColumnConfig } from "./KanbanColumnConfig";

interface Props {
  column: KanbanColumnType;
  cards: KanbanCardType[];
  tenders: Record<string, Tender>;
  onRename: (id: string, name: string) => void;
  onRecolor: (id: string, color: string) => void;
  onDelete: (id: string) => void;
  onReorder?: (direction: "left" | "right") => void;
  canMoveLeft?: boolean;
  canMoveRight?: boolean;
  onAddCard: (tender_id: string, column_id: string, tender: Tender) => Promise<void>;
  onRemoveCard: (tender_id: string) => void;
  /** IDs de licitaciones ya presentes en cualquier columna del tablero del
   *  usuario. Se usa en el modal "Agregar licitación" para ocultar guardadas
   *  duplicadas. El padre (KanbanBoard) lo construye desde `cards`. */
  boardTenderIds: string[];
}

export function KanbanColumn({
  column,
  cards,
  tenders,
  onRename,
  onRecolor,
  onDelete,
  onReorder,
  canMoveLeft,
  canMoveRight,
  onAddCard,
  onRemoveCard,
  boardTenderIds,
}: Props) {
  const [showConfig, setShowConfig] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const configAreaRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!showConfig) return;
    const handleMouseDown = (e: MouseEvent) => {
      if (configAreaRef.current && !configAreaRef.current.contains(e.target as Node)) {
        setShowConfig(false);
      }
    };
    document.addEventListener("mousedown", handleMouseDown);
    return () => document.removeEventListener("mousedown", handleMouseDown);
  }, [showConfig]);

  const cardIds = cards.map((c) => c.id);

  const { setNodeRef, isOver } = useDroppable({ id: column.id });

  const columnStyle = {
    borderColor: isOver ? undefined : column.color,
    backgroundColor: column.color + "14",
  };

  return (
    <section
      aria-label={column.name}
      style={columnStyle}
      className={`group flex flex-col w-[302px] flex-none h-full rounded-lg border transition-all duration-200 ${
        isOver ? "border-primary ring-[3px] ring-primary/20" : ""
      }`}
    >
      <div className="px-3.5 pt-3 pb-2">
        <div ref={configAreaRef}>
          <div className="flex items-center gap-2">
            <h2 className="flex-1 font-display text-[15px] font-bold text-text-strong truncate">
              {column.name}
            </h2>
            <span className="h-5 px-2 rounded-full text-xs font-semibold tabular-nums bg-warm-200 text-text-body flex items-center flex-none">
              {column.card_count}
            </span>
            <button
              type="button"
              onClick={() => setShowConfig((v) => !v)}
              className={`flex-none p-1 rounded transition-colors ${
                showConfig
                  ? "text-primary bg-primary/10"
                  : "text-text-subtle hover:text-text-strong hover:bg-warm-100"
              }`}
              aria-label="Configurar columna"
            >
              <Icon name="settings" size={14} />
            </button>
          </div>

          {showConfig && (
            <KanbanColumnConfig
              column={column}
              onRename={onRename}
              onRecolor={onRecolor}
              onDelete={onDelete}
              onClose={() => setShowConfig(false)}
              onReorder={onReorder}
              canMoveLeft={canMoveLeft}
              canMoveRight={canMoveRight}
            />
          )}
        </div>
      </div>

      <div
        ref={setNodeRef}
        className="flex-1 px-2 pb-2 flex flex-col gap-2 overflow-y-auto"
      >
        <SortableContext items={cardIds} strategy={verticalListSortingStrategy}>
          {cards.map((card) => (
            <KanbanCard
              key={card.id}
              card={card}
              tender={tenders[card.tender_id]}
              onRemove={onRemoveCard}
            />
          ))}
        </SortableContext>
        <button
          type="button"
          onClick={() => setShowAddModal(true)}
          className="opacity-0 group-hover:opacity-100 flex items-center gap-1 py-1.5 px-1 text-sm text-text-muted hover:text-primary rounded-md hover:bg-surface-card w-full transition-all duration-200"
        >
          <Icon name="plus" size={14} />
          Agregar
        </button>
      </div>

      {showAddModal && (
        <AddTenderModal
          columnId={column.id}
          columnName={column.name}
          boardTenderIds={boardTenderIds}
          onAdd={onAddCard}
          onClose={() => setShowAddModal(false)}
        />
      )}
    </section>
  );
}
