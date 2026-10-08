"use client";

import React, { useState } from "react";
import {
  DndContext,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
  arrayMove,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Dialog } from "@/features/shared/components/Dialog";
import { Icon } from "@/features/shared/components/Icon";
import type { KanbanColumn } from "../kanbanTypes";
import { PALETTE } from "../constants";

interface KanbanBoardEditorProps {
  open: boolean;
  columns: KanbanColumn[];
  onClose: () => void;
  onRename: (id: string, name: string) => void | Promise<void>;
  onRecolor: (id: string, color: string) => void | Promise<void>;
  onDelete: (id: string) => void | Promise<void>;
  onAddColumn: (name: string) => void | Promise<void>;
  onReorder: (orderedIds: string[]) => void | Promise<void>;
}

interface EditorRowProps {
  column: KanbanColumn;
  onRename: (id: string, name: string) => void | Promise<void>;
  onRecolor: (id: string, color: string) => void | Promise<void>;
  onDelete: (id: string) => void | Promise<void>;
}

function EditorRow({ column, onRename, onRecolor, onDelete }: EditorRowProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: column.id });
  const [nameValue, setNameValue] = useState(column.name);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  const commitName = () => {
    const trimmed = nameValue.trim();
    if (trimmed && trimmed !== column.name) {
      void onRename(column.id, trimmed);
    } else {
      setNameValue(column.name);
    }
  };

  const handleDeleteClick = () => {
    if (column.card_count > 0) {
      setConfirmingDelete(true);
    } else {
      void onDelete(column.id);
    }
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      data-testid={`editor-row-${column.id}`}
      className="flex items-center gap-2 rounded-md border border-border-subtle bg-surface-card p-2"
    >
      <button
        type="button"
        aria-label="Reordenar columna"
        {...attributes}
        {...listeners}
        className="flex-none cursor-grab touch-none p-1 text-text-subtle hover:text-text-strong"
      >
        <Icon name="grip-vertical" size={16} />
      </button>

      <input
        type="text"
        value={nameValue}
        onChange={(e) => setNameValue(e.target.value)}
        onBlur={commitName}
        onKeyDown={(e) => {
          if (e.key === "Enter") (e.target as HTMLInputElement).blur();
          if (e.key === "Escape") {
            setNameValue(column.name);
            (e.target as HTMLInputElement).blur();
          }
        }}
        aria-label={`Nombre de la columna ${column.name}`}
        className="min-w-0 flex-1 rounded-md border border-border-subtle px-2 py-1 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
      />

      <div className="flex flex-none items-center gap-1">
        {PALETTE.map((color) => (
          <button
            key={color}
            type="button"
            onClick={() => void onRecolor(column.id, color)}
            aria-label={`Color ${color}`}
            style={{ backgroundColor: color }}
            className={`h-4 w-4 rounded-full transition-all duration-150 ${
              column.color.toUpperCase() === color
                ? "ring-2 ring-offset-1 ring-text-strong scale-110"
                : "opacity-80 hover:scale-110 hover:opacity-100"
            }`}
          />
        ))}
      </div>

      <button
        type="button"
        onClick={handleDeleteClick}
        aria-label={`Eliminar columna ${column.name}`}
        className="flex-none rounded p-1 text-text-subtle hover:text-danger"
      >
        <Icon name="trash-2" size={14} />
      </button>

      {confirmingDelete && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40"
          onClick={() => setConfirmingDelete(false)}
        >
          <div
            role="alertdialog"
            aria-labelledby={`confirm-delete-${column.id}`}
            className="w-[90%] max-w-sm rounded-lg border border-border-subtle bg-surface-card p-5 shadow-lg"
            onClick={(e) => e.stopPropagation()}
          >
            <h3
              id={`confirm-delete-${column.id}`}
              className="font-display text-base font-bold text-text-strong mb-2"
            >
              Eliminar columna
            </h3>
            <p className="text-sm text-text-body mb-4">
              La columna <strong>{column.name}</strong> tiene {column.card_count}{" "}
              tarjeta{column.card_count !== 1 ? "s" : ""}. ¿Eliminarla de todas
              formas?
            </p>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setConfirmingDelete(false)}
                className="px-3 py-1.5 text-sm text-text-subtle hover:text-text-strong rounded-md hover:bg-warm-100"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={() => {
                  setConfirmingDelete(false);
                  void onDelete(column.id);
                }}
                className="px-3 py-1.5 text-sm font-semibold bg-danger text-on-primary rounded-md hover:opacity-90"
              >
                Eliminar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export function KanbanBoardEditor({
  open,
  columns,
  onClose,
  onRename,
  onRecolor,
  onDelete,
  onAddColumn,
  onReorder,
}: KanbanBoardEditorProps) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = columns.findIndex((c) => c.id === active.id);
    const newIndex = columns.findIndex((c) => c.id === over.id);
    if (oldIndex === -1 || newIndex === -1) return;
    const reordered = arrayMove(columns, oldIndex, newIndex).map((c) => c.id);
    void onReorder(reordered);
  };

  const handleAddColumn = () => {
    void onAddColumn("Nueva columna");
  };

  return (
    <Dialog open={open} title="Editar tablero" onClose={onClose}>
      <div className="space-y-3">
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={columns.map((c) => c.id)}
            strategy={verticalListSortingStrategy}
          >
            <div className="flex flex-col gap-2">
              {columns.map((column) => (
                <EditorRow
                  key={column.id}
                  column={column}
                  onRename={onRename}
                  onRecolor={onRecolor}
                  onDelete={onDelete}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>

        <button
          type="button"
          onClick={handleAddColumn}
          className="flex w-full items-center justify-center gap-2 rounded-md border border-dashed border-border-subtle px-3 py-2 text-sm text-text-muted transition-colors hover:border-primary hover:text-primary"
        >
          <Icon name="plus" size={14} />
          Agregar columna
        </button>

        <div className="flex justify-end pt-2">
          <button
            type="button"
            onClick={onClose}
            className="text-sm font-semibold text-primary hover:text-primary-hover"
          >
            Cerrar
          </button>
        </div>
      </div>
    </Dialog>
  );
}

// Exposed for unit tests of the reorder handler without a real drag.
export function _computeReorderedIds(
  columns: KanbanColumn[],
  activeId: string,
  overId: string,
): string[] | null {
  const oldIndex = columns.findIndex((c) => c.id === activeId);
  const newIndex = columns.findIndex((c) => c.id === overId);
  if (oldIndex === -1 || newIndex === -1 || oldIndex === newIndex) return null;
  return arrayMove(columns, oldIndex, newIndex).map((c) => c.id);
}
