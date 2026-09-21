"use client";

import React, { useRef, useState } from "react";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { Icon } from "@/features/shared/components/Icon";
import type { KanbanCard as KanbanCardType } from "../kanbanTypes";
import { useKanban } from "../hooks/useKanban";
import { KanbanCard } from "./KanbanCard";
import { KanbanColumn } from "./KanbanColumn";

export function KanbanBoard() {
  const {
    columns,
    cards,
    tenders,
    loading,
    error,
    addColumn,
    renameColumn,
    deleteColumn,
    addCard,
    moveCard,
    removeCard,
  } = useKanban();

  const [addingColumn, setAddingColumn] = useState(false);
  const [newColumnName, setNewColumnName] = useState("");
  const [addingColLoading, setAddingColLoading] = useState(false);
  const [activeCard, setActiveCard] = useState<KanbanCardType | null>(null);
  const newColInputRef = useRef<HTMLInputElement>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
  );

  function handleDragStart({ active }: DragStartEvent) {
    const card = cards.find((c) => c.id === active.id);
    setActiveCard(card ?? null);
  }

  function handleDragEnd({ active, over }: DragEndEvent) {
    setActiveCard(null);
    if (!over) return;

    const draggedCard = cards.find((c) => c.id === active.id);
    if (!draggedCard) return;

    const isOverColumn = columns.some((col) => col.id === over.id);
    let targetColumnId: string;
    let targetPosition: number;

    if (isOverColumn) {
      targetColumnId = over.id as string;
      targetPosition = cards.filter(
        (c) => c.column_id === targetColumnId,
      ).length;
    } else {
      const overCard = cards.find((c) => c.id === over.id);
      if (!overCard) return;
      targetColumnId = overCard.column_id;
      targetPosition = overCard.position;
    }

    if (
      draggedCard.column_id === targetColumnId &&
      draggedCard.position === targetPosition
    ) {
      return;
    }

    void moveCard(draggedCard.tender_id, targetColumnId, targetPosition);
  }

  const handleAddColumnSubmit = async () => {
    const name = newColumnName.trim();
    if (!name) return;
    setAddingColLoading(true);
    try {
      await addColumn(name);
      setNewColumnName("");
      setAddingColumn(false);
    } finally {
      setAddingColLoading(false);
    }
  };

  const handleAddColumnKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") void handleAddColumnSubmit();
    if (e.key === "Escape") {
      setNewColumnName("");
      setAddingColumn(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-text-subtle">
        <span className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-sm text-danger">{error}</p>
      </div>
    );
  }

  const cardsInColumn = (columnId: string) =>
    cards
      .filter((c) => c.column_id === columnId)
      .sort((a, b) => a.position - b.position);

  return (
    <div className="flex flex-col h-full">
      <div className="px-6 py-4 border-b border-border-subtle">
        <h1 className="font-display text-2xl font-bold text-text-strong">Tablero</h1>
        <p className="text-sm text-text-subtle mt-0.5">
          Organiza tus licitaciones en etapas de trabajo
        </p>
      </div>

      <div className="flex-1 overflow-x-auto px-6 py-5">
        <DndContext
          sensors={sensors}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
        >
          <div className="flex gap-3 h-full">
            {columns.map((column) => (
              <KanbanColumn
                key={column.id}
                column={column}
                cards={cardsInColumn(column.id)}
                tenders={tenders}
                onRename={(id, name) => void renameColumn(id, name)}
                onDelete={(id) => void deleteColumn(id)}
                onAddCard={addCard}
                onRemoveCard={(tender_id) => void removeCard(tender_id)}
              />
            ))}

            <div className="flex-none w-[302px] self-start">
              {addingColumn ? (
                <div className="bg-bg-sunken rounded-lg border border-border-subtle p-3">
                  <input
                    ref={newColInputRef}
                    type="text"
                    value={newColumnName}
                    onChange={(e) => setNewColumnName(e.target.value)}
                    onKeyDown={handleAddColumnKeyDown}
                    placeholder="Nombre de la columna"
                    className="w-full text-sm border border-border-subtle rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary mb-2"
                    autoFocus
                    disabled={addingColLoading}
                  />
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => void handleAddColumnSubmit()}
                      disabled={addingColLoading || !newColumnName.trim()}
                      className="flex-1 text-sm font-semibold py-1.5 rounded-md bg-primary text-on-primary hover:bg-primary-hover transition-colors disabled:opacity-50"
                    >
                      {addingColLoading ? (
                        <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent inline-block" />
                      ) : (
                        "Agregar"
                      )}
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setNewColumnName("");
                        setAddingColumn(false);
                      }}
                      className="px-3 py-1.5 text-sm text-text-subtle hover:text-text-strong rounded-md hover:bg-warm-100 transition-colors"
                    >
                      <Icon name="x" size={16} />
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => setAddingColumn(true)}
                  className="w-full flex items-center gap-2 px-4 py-3 text-sm text-text-muted hover:text-primary bg-bg-sunken/60 hover:bg-bg-sunken rounded-lg border border-dashed border-border-subtle hover:border-primary transition-all duration-200"
                >
                  <Icon name="plus" size={16} />
                  Nueva columna
                </button>
              )}
            </div>
          </div>

          <DragOverlay>
            {activeCard ? (
              <div className="rotate-2 shadow-lg">
                <KanbanCard
                  card={activeCard}
                  tender={tenders[activeCard.tender_id]}
                  onRemove={() => undefined}
                />
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      </div>
    </div>
  );
}
