"use client";

import React, { useEffect, useRef, useState } from "react";
import { Icon } from "@/features/shared/components/Icon";
import type { KanbanColumn } from "../kanbanTypes";

const PALETTE = [
  "#A99A7C",
  "#BF6E4A",
  "#5C7A52",
  "#35645B",
  "#E08E2B",
  "#A65A2E",
  "#244024",
];

const HEX_RE = /^#[0-9A-Fa-f]{6}$/;

interface Props {
  column: KanbanColumn;
  onRename: (id: string, name: string) => void;
  onRecolor: (id: string, color: string) => void;
  onDelete: (id: string) => void;
  onClose: () => void;
  onReorder?: (direction: "left" | "right") => void;
  canMoveLeft?: boolean;
  canMoveRight?: boolean;
}

export function KanbanColumnConfig({ column, onRename, onRecolor, onDelete, onClose, onReorder, canMoveLeft, canMoveRight }: Props) {
  const [nameValue, setNameValue] = useState(column.name);
  const [hexValue, setHexValue] = useState(column.color);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const nameInputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const idleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
  }, []);

  const handleMouseEnter = () => {
    if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
  };

  const handleMouseLeave = () => {
    if (containerRef.current?.matches(":focus-within")) return;
    idleTimerRef.current = setTimeout(onClose, 1500);
  };

  const handleSave = () => {
    const trimmed = nameValue.trim();
    if (trimmed && trimmed !== column.name) {
      onRename(column.id, trimmed);
    }
    onClose();
  };

  const handleNameKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSave();
    if (e.key === "Escape") onClose();
  };

  const applyColor = (color: string) => {
    setHexValue(color);
    onRecolor(column.id, color);
  };

  const handleHexInput = (val: string) => {
    setHexValue(val);
    if (HEX_RE.test(val)) {
      onRecolor(column.id, val.toUpperCase());
    }
  };

  const handleDeleteClick = () => {
    if (column.card_count > 0) {
      setShowDeleteConfirm(true);
    } else {
      onDelete(column.id);
    }
  };

  return (
    <div
      ref={containerRef}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className="mt-2 rounded-md bg-surface-card border border-border-default shadow-md p-3 space-y-3"
    >
      <div>
        <label className="text-[11px] font-semibold text-text-subtle uppercase tracking-wide mb-1 block">
          Nombre
        </label>
        <input
          ref={nameInputRef}
          type="text"
          value={nameValue}
          onChange={(e) => setNameValue(e.target.value)}
          onKeyDown={handleNameKeyDown}
          autoFocus
          className="w-full text-sm border border-border-subtle rounded-md px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
        />
      </div>

      <div>
        <label className="text-[11px] font-semibold text-text-subtle uppercase tracking-wide mb-1.5 block">
          Color
        </label>
        <div className="flex items-center gap-1.5 mb-2">
          {PALETTE.map((color) => (
            <button
              key={color}
              type="button"
              onClick={() => applyColor(color)}
              style={{ backgroundColor: color }}
              className={`w-5 h-5 rounded-full transition-all duration-150 ${
                hexValue.toUpperCase() === color
                  ? "ring-2 ring-offset-1 ring-text-strong scale-110"
                  : "hover:scale-110 opacity-80 hover:opacity-100"
              }`}
              aria-label={color}
            />
          ))}
        </div>
        <div className="flex items-center gap-2">
          <input
            type="color"
            value={HEX_RE.test(hexValue) ? hexValue : "#A99A7C"}
            onChange={(e) => applyColor(e.target.value.toUpperCase())}
            className="w-7 h-7 rounded border border-border-subtle cursor-pointer p-0.5 bg-transparent"
            title="Selector de color"
          />
          <input
            type="text"
            value={hexValue}
            onChange={(e) => handleHexInput(e.target.value)}
            maxLength={7}
            placeholder="#RRGGBB"
            className="flex-1 text-xs font-mono border border-border-subtle rounded-md px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
          />
        </div>
      </div>

      <div className="pt-2 border-t border-border-subtle flex items-center justify-between">
        <button
          type="button"
          onClick={handleSave}
          className="text-sm font-semibold text-primary hover:text-primary-hover transition-colors"
        >
          Guardar
        </button>

        {onReorder && (
          <div className="flex items-center gap-0.5">
            <button
              type="button"
              onClick={() => onReorder("left")}
              disabled={!canMoveLeft}
              className="p-1 rounded text-text-subtle hover:text-text-strong hover:bg-warm-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              aria-label="Mover columna a la izquierda"
            >
              <Icon name="chevron-left" size={14} />
            </button>
            <button
              type="button"
              onClick={() => onReorder("right")}
              disabled={!canMoveRight}
              className="p-1 rounded text-text-subtle hover:text-text-strong hover:bg-warm-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              aria-label="Mover columna a la derecha"
            >
              <Icon name="chevron-right" size={14} />
            </button>
          </div>
        )}

        {showDeleteConfirm ? (
          <div className="flex items-center gap-2 text-xs">
            <span className="text-text-subtle">
              ¿Eliminar con {column.card_count} tarjeta{column.card_count !== 1 ? "s" : ""}?
            </span>
            <button
              type="button"
              onClick={() => { setShowDeleteConfirm(false); onDelete(column.id); }}
              className="font-semibold text-danger hover:underline"
            >
              Sí
            </button>
            <button
              type="button"
              onClick={() => setShowDeleteConfirm(false)}
              className="text-text-subtle hover:text-text-strong"
            >
              No
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={handleDeleteClick}
            className="flex items-center gap-1 text-xs text-text-subtle hover:text-danger transition-colors"
          >
            <Icon name="trash-2" size={12} />
            Eliminar columna
          </button>
        )}
      </div>
    </div>
  );
}
