"use client";

import React from "react";
import { Icon } from "@/features/shared/components/Icon";

interface SearchPaginationProps {
  page: number;
  total: number;
  pageSize: number;
  onPageChange: (page: number) => void;
}

export function SearchPagination({
  page,
  total,
  pageSize,
  onPageChange,
}: SearchPaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  if (totalPages <= 1) return null;

  return (
    <div className="mt-8 flex items-center justify-between border-t border-border-subtle pt-6">
      <button
        type="button"
        onClick={() => onPageChange(Math.max(1, page - 1))}
        disabled={page <= 1}
        className="inline-flex items-center gap-1.5 rounded-md border border-border-subtle bg-surface-card px-4 py-2 text-sm font-semibold text-text-strong hover:bg-surface-hover disabled:opacity-40 disabled:hover:bg-surface-card transition-colors cursor-pointer disabled:cursor-not-allowed"
      >
        <Icon name="chevron-left" size={16} />
        Anterior
      </button>

      <span className="text-sm font-medium text-text-muted">
        Página <span className="font-semibold text-text-strong">{page}</span> de{" "}
        <span className="font-semibold text-text-strong">{totalPages}</span>
      </span>

      <button
        type="button"
        onClick={() => onPageChange(Math.min(totalPages, page + 1))}
        disabled={page >= totalPages}
        className="inline-flex items-center gap-1.5 rounded-md border border-border-subtle bg-surface-card px-4 py-2 text-sm font-semibold text-text-strong hover:bg-surface-hover disabled:opacity-40 disabled:hover:bg-surface-card transition-colors cursor-pointer disabled:cursor-not-allowed"
      >
        Siguiente
        <Icon name="chevron-right" size={16} />
      </button>
    </div>
  );
}
