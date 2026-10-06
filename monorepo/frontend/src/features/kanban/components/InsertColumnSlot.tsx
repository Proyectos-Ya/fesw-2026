"use client";

import React, { useRef, useState } from "react";
import { Icon } from "@/features/shared/components/Icon";

interface Props {
  onInsert: (name: string) => Promise<void>;
}

export function InsertColumnSlot({ onInsert }: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const open = () => setIsOpen(true);

  const close = () => {
    setIsOpen(false);
    setName("");
  };

  const handleSubmit = async () => {
    const trimmed = name.trim();
    if (!trimmed || loading) return;
    setLoading(true);
    try {
      await onInsert(trimmed);
      close();
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") void handleSubmit();
    if (e.key === "Escape") close();
  };

  if (isOpen) {
    return (
      <div className="flex-none w-[302px] self-start bg-bg-sunken rounded-lg border border-border-subtle p-3 mx-1.5">
        <input
          ref={inputRef}
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Nombre de la columna"
          className="w-full text-sm border border-border-subtle rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary mb-2"
          autoFocus
          disabled={loading}
        />
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => void handleSubmit()}
            disabled={loading || !name.trim()}
            className="flex-1 text-sm font-semibold py-1.5 rounded-md bg-primary text-on-primary hover:bg-primary-hover transition-colors disabled:opacity-50"
          >
            {loading ? (
              <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent inline-block" />
            ) : (
              "Agregar"
            )}
          </button>
          <button
            type="button"
            onClick={close}
            className="px-3 py-1.5 text-sm text-text-subtle hover:text-text-strong rounded-md hover:bg-warm-100 transition-colors"
          >
            <Icon name="x" size={16} />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label="Insertar columna aquí"
      onClick={open}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") open(); }}
      className="group/insert flex-none self-stretch w-4 relative flex items-center justify-center cursor-pointer"
    >
      <span className="absolute inset-y-0 left-1/2 -translate-x-1/2 w-px bg-transparent group-hover/insert:bg-primary/30 transition-colors duration-150" />
      <span className="relative z-10 opacity-0 group-hover/insert:opacity-100 transition-opacity duration-150 w-5 h-5 rounded-full bg-bg-page border border-primary/50 shadow-sm flex items-center justify-center text-primary">
        <Icon name="plus" size={9} />
      </span>
    </div>
  );
}
