"use client";

import React, { useRef, useState } from "react";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { useDroppable } from "@dnd-kit/core";
import type { Tender } from "@/features/matches/tenderTypes";
import { Icon } from "@/features/shared/components/Icon";
import type { KanbanCard as KanbanCardType, KanbanColumn as KanbanColumnType } from "../kanbanTypes";
import { AddTenderModal } from "./AddTenderModal";
import { DeleteColumnDialog } from "./DeleteColumnDialog";
import { KanbanCard } from "./KanbanCard";

interface Props {
  column: KanbanColumnType;
  cards: KanbanCardType[];
  tenders: Record<string, Tender>;
  onRename: (id: string, name: string) => void;
  onDelete: (id: string) => void;
  onAddCard: (tender_id: string, column_id: string, tender: Tender) => Promise<void>;
  onRemoveCard: (tender_id: string) => void;
}

export function KanbanColumn({
  column,
  cards,
  tenders,
  onRename,
  onDelete,
  onAddCard,
  onRemoveCard,
}: Props) {
  const [editing, setEditing] = useState(false);
  const [nameValue, setNameValue] = useState(column.name);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const cardIds = cards.map((c) => c.id);

  const { setNodeRef, isOver } = useDroppable({ id: column.id });

  const handleNameBlur = () => {
    setEditing(false);
    const trimmed = nameValue.trim();
    if (trimmed && trimmed !== column.name) {
      onRename(column.id, trimmed);
    } else {
      setNameValue(column.name);
    }
  };

  const handleNameKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") inputRef.current?.blur();
    if (e.key === "Escape") {
      setNameValue(column.name);
      setEditing(false);
    }
  };

  const handleDeleteClick = () => {
    if (column.card_count > 0) {
      setShowDeleteDialog(true);
    } else {
      onDelete(column.id);
    }
  };

  return (
    <section
      aria-label={column.name}
      className={`group flex flex-col w-[302px] flex-none h-full bg-bg-sunken rounded-lg border transition-all duration-200 ${
        isOver
          ? "border-primary ring-[3px] ring-primary/20"
          : "border-border-subtle"
      }`}
    >
      <div className="px-3.5 pt-3 pb-2">
        <div className="flex items-center gap-2">
          {editing ? (
            <input
              ref={inputRef}
              value={nameValue}
              onChange={(e) => setNameValue(e.target.value)}
              onBlur={handleNameBlur}
              onKeyDown={handleNameKeyDown}
              className="flex-1 font-display text-[15px] font-bold text-text-strong bg-white border border-primary rounded px-2 py-0.5 focus:outline-none focus:ring-2 focus:ring-primary/30"
              autoFocus
            />
          ) : (
            <h2
              onClick={() => setEditing(true)}
              className="flex-1 font-display text-[15px] font-bold text-text-strong truncate cursor-pointer hover:text-primary transition-colors"
              title="Clic para renombrar"
            >
              {column.name}
            </h2>
          )}
          <span className="h-5 px-2 rounded-full text-xs font-semibold tabular-nums bg-warm-200 text-text-body flex items-center flex-none">
            {column.card_count}
          </span>
          <button
            type="button"
            onClick={handleDeleteClick}
            className="flex-none p-1 text-text-subtle hover:text-danger hover:bg-danger-soft rounded transition-colors"
            aria-label="Eliminar columna"
          >
            <Icon name="trash-2" size={14} />
          </button>
        </div>

        {showDeleteDialog && (
          <DeleteColumnDialog
            cardCount={column.card_count}
            onConfirm={() => {
              setShowDeleteDialog(false);
              onDelete(column.id);
            }}
            onCancel={() => setShowDeleteDialog(false)}
          />
        )}
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
          onAdd={onAddCard}
          onClose={() => setShowAddModal(false)}
        />
      )}
    </section>
  );
}
