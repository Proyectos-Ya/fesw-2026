"use client";

import React from "react";
import { Icon } from "@/features/shared/components/Icon";

interface SearchBarProps {
  value: string;
  onChange: (value: string) => void;
  isLoading?: boolean;
  placeholder?: string;
}

export function SearchBar({
  value,
  onChange,
  isLoading = false,
  placeholder = "Buscar licitaciones por descripción, producto, institución o código...",
}: SearchBarProps) {
  const handleClear = () => {
    onChange("");
  };

  return (
    <div className="relative w-full">
      <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-4 text-text-subtle">
        {isLoading ? (
          <span className="size-5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        ) : (
          <Icon name="search" size={20} />
        )}
      </div>

      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        aria-label="Buscar licitaciones"
        className="w-full rounded-lg border border-border-subtle bg-surface-card py-3.5 pl-12 pr-11 text-base text-text-strong placeholder:text-text-muted transition-all duration-200 focus:border-primary focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary/20 shadow-xs"
      />

      {value.trim().length > 0 && (
        <button
          type="button"
          onClick={handleClear}
          aria-label="Limpiar búsqueda"
          className="absolute inset-y-0 right-0 flex items-center pr-3.5 text-text-subtle hover:text-text-strong transition-colors cursor-pointer"
        >
          <div className="flex size-7 items-center justify-center rounded-full hover:bg-warm-100">
            <Icon name="x" size={16} />
          </div>
        </button>
      )}
    </div>
  );
}