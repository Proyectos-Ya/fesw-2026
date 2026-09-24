"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { searchTenders } from "@/features/search/services/searchService";
import type { Tender } from "@/features/matches/tenderTypes";
import { daysUntilClosing } from "@/features/matches/utils/format";
import { Badge } from "@/features/shared/components/Badge";
import { Icon } from "@/features/shared/components/Icon";
import { ApiError } from "@/features/shared/api/client";

interface Props {
  columnId: string;
  columnName: string;
  onAdd: (tender_id: string, column_id: string, tender: Tender) => Promise<void>;
  onClose: () => void;
}

const CLOSING_TONE_MAP = {
  danger: "danger",
  warning: "warning",
  neutral: "neutral",
  expired: "neutral",
} as const;

export function AddTenderModal({ columnId, columnName, onAdd, onClose }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Tender[]>([]);
  const [searching, setSearching] = useState(false);
  const [adding, setAdding] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const search = useCallback(async (q: string) => {
    if (!q.trim()) {
      setResults([]);
      return;
    }
    setSearching(true);
    try {
      const result = await searchTenders({ q, limit: 10 });
      setResults(result.items);
    } catch {
      setResults([]);
    } finally {
      setSearching(false);
    }
  }, []);

  const handleQueryChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setQuery(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => void search(val), 350);
  };

  const handleAdd = async (tender: Tender) => {
    setAdding(tender.id);
    setError(null);
    try {
      await onAdd(tender.id, columnId, tender);
      onClose();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError("Esta licitación ya está en tu tablero.");
      } else {
        setError("No se pudo agregar la licitación.");
      }
      setAdding(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
        aria-hidden
      />
      <div className="relative w-full max-w-lg bg-white rounded-xl shadow-xl flex flex-col max-h-[80vh]">
        <div className="flex items-center justify-between p-4 border-b border-border-subtle">
          <div>
            <h2 className="text-base font-semibold text-text-strong">
              Agregar licitación
            </h2>
            <p className="text-xs text-text-subtle mt-0.5">en {columnName}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-md text-text-subtle hover:bg-warm-100 transition-colors"
            aria-label="Cerrar"
          >
            <Icon name="x" size={18} />
          </button>
        </div>

        <div className="p-4 border-b border-border-subtle">
          <div className="relative">
            <Icon
              name="search"
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-text-subtle pointer-events-none"
            />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={handleQueryChange}
              placeholder="Buscar licitación por nombre o código..."
              className="w-full pl-9 pr-4 py-2.5 text-sm border border-border-subtle rounded-md focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
            />
            {searching && (
              <span className="absolute right-3 top-1/2 -translate-y-1/2">
                <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-primary border-t-transparent inline-block" />
              </span>
            )}
          </div>
          {error && (
            <p className="mt-2 text-xs text-danger">{error}</p>
          )}
        </div>

        <div className="overflow-y-auto flex-1">
          {results.length === 0 && query.trim() && !searching && (
            <p className="p-4 text-sm text-text-subtle text-center">
              Sin resultados para &quot;{query}&quot;
            </p>
          )}
          {results.length === 0 && !query.trim() && (
            <p className="p-4 text-sm text-text-subtle text-center">
              Escribe para buscar licitaciones
            </p>
          )}
          {results.map((tender) => {
            const closing = daysUntilClosing(tender.closing_at);
            return (
              <button
                key={tender.id}
                type="button"
                disabled={adding === tender.id}
                onClick={() => void handleAdd(tender)}
                className="w-full text-left px-4 py-3 hover:bg-warm-50 border-b border-border-subtle last:border-0 transition-colors disabled:opacity-50"
              >
                <div className="flex items-start gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-[11px] text-text-subtle font-mono truncate mb-0.5">
                      {tender.code}
                    </p>
                    <p className="text-sm font-medium text-text-strong line-clamp-2 leading-snug">
                      {tender.name}
                    </p>
                    {tender.buyer_name && (
                      <p className="text-xs text-text-subtle mt-0.5 truncate">
                        {tender.buyer_name}
                      </p>
                    )}
                  </div>
                  <div className="flex-none flex flex-col items-end gap-1">
                    <Badge tone={CLOSING_TONE_MAP[closing.tone]}>
                      {closing.label}
                    </Badge>
                    {adding === tender.id && (
                      <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-primary border-t-transparent inline-block" />
                    )}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
