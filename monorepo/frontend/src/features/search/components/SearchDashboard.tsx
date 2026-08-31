"use client";

import React from "react";
import { useTenderSearch } from "../hooks/useTenderSearch";
import { SearchBar } from "./SearchBar";
import { SearchFilters } from "./SearchFilters";
import { SearchPagination } from "./SearchPagination";
import { TenderCard } from "@/features/matches/components/TenderCard";
import { TenderCardSkeleton } from "@/features/matches/components/TenderCardSkeleton";
import { Icon } from "@/features/shared/components/Icon";
import { Button } from "@/features/shared/components/Button";

export function SearchDashboard() {
  const {
    inputText,
    setInputText,
    regions,
    setRegions,
    availability,
    setAvailability,
    minAmount,
    maxAmount,
    setAmountRange,
    page,
    setPage,
    pageSize,
    clearFilters,
    hasActiveFilters,
    state,
    retry,
    savedTenderIds,
    toggleSave,
    actionError,
    clearActionError,
  } = useTenderSearch();

  const { items, total, isTruncated, isLoading, error, isServiceUnavailable } = state;

  return (
    <section className="mx-auto w-full max-w-3xl space-y-6">
      {/* Header */}
      <div>
        <div className="eyebrow mb-2">Buscador Directo</div>
        <h1 className="font-display text-3xl font-bold tracking-tight text-text-strong sm:text-4xl">
          Explorador de Licitaciones
        </h1>
        <p className="mt-2 text-base text-text-muted">
          Busca y filtra entre todas las compras públicas y licitaciones disponibles.
        </p>
      </div>

      {/* Non-blocking Service/Network Error Banner (HdU 07.5) */}
      {error && (
        <div
          role="alert"
          className="flex items-start justify-between gap-4 rounded-lg border border-warning/30 bg-warning-soft/30 p-4 text-warning"
        >
          <div className="flex items-start gap-3">
            <Icon name="alert-triangle" size={20} className="text-warning flex-none mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-text-strong">
                {isServiceUnavailable
                  ? "El motor de búsqueda no está disponible en este momento."
                  : "Ocurrió un problema al realizar la búsqueda."}
              </p>
              <p className="mt-1 text-xs text-text-muted">
                {error} Inténtalo nuevamente en unos instantes.
              </p>
            </div>
          </div>
          <Button
            type="button"
            variant="ghost"
            onClick={retry}
            className="text-xs font-bold text-primary hover:bg-primary-soft shrink-0"
          >
            Reintentar
          </Button>
        </div>
      )}

      {/* Action Error Banner (e.g. save tender failed) */}
      {actionError && (
        <div className="flex items-center justify-between rounded-md border border-danger/20 bg-danger-soft/30 p-4 text-sm font-medium text-danger">
          <span>{actionError}</span>
          <button
            type="button"
            onClick={clearActionError}
            className="ml-4 text-xs font-bold underline hover:opacity-80 cursor-pointer"
          >
            Cerrar
          </button>
        </div>
      )}

      {/* Search Bar Input */}
      <SearchBar
        value={inputText}
        onChange={setInputText}
        isLoading={isLoading}
      />

      {/* Advanced Filters */}
      <SearchFilters
        regions={regions}
        onRegionsChange={setRegions}
        availability={availability}
        onAvailabilityChange={setAvailability}
        minAmount={minAmount}
        maxAmount={maxAmount}
        onAmountRangeChange={setAmountRange}
        onClearFilters={clearFilters}
        hasActiveFilters={hasActiveFilters}
      />

      {/* Results Header / Counter */}
      <div className="flex flex-wrap items-center justify-between gap-2 pt-2">
        <p className="text-sm font-medium text-text-muted">
          {isLoading
            ? "Buscando licitaciones..."
            : total === 0
              ? "No se encontraron licitaciones."
              : total === 1
                ? "Se encontró 1 licitación."
                : `Se encontraron ${total.toLocaleString("es-CL")} licitaciones.`}
        </p>
      </div>

      {/* Truncated notice banner (HdU 07.4) */}
      {!isLoading && isTruncated && (
        <div className="flex items-center gap-3 rounded-lg border border-info/20 bg-info-soft/30 p-4 text-xs text-text-muted">
          <Icon name="info" size={18} className="text-blue-500 flex-none" />
          <span>
            Se superó el límite de resultados para esta consulta. Te recomendamos afinar
            los filtros de búsqueda o especificar términos para ver resultados más precisos.
          </span>
        </div>
      )}

      {/* Results List */}
      {isLoading ? (
        <div className="flex flex-col gap-4">
          <TenderCardSkeleton />
          <TenderCardSkeleton />
          <TenderCardSkeleton />
        </div>
      ) : total === 0 ? (
        /* Empty State (HdU 07.3) */
        <div className="rounded-lg border border-border-subtle bg-surface-card p-10 text-center shadow-xs">
          <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-full bg-warm-100">
            <Icon name="search" size={22} color="var(--text-subtle)" />
          </div>
          <h2 className="font-display text-xl font-semibold text-text-strong">
            Sin resultados para tu búsqueda
          </h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-text-muted">
            {hasActiveFilters
              ? "Intenta buscando con términos más generales o flexibilizando los filtros de región, estado y presupuesto."
              : "No se encontraron licitaciones publicadas en este momento."}
          </p>
          {hasActiveFilters && (
            <button
              type="button"
              onClick={clearFilters}
              className="mt-5 inline-flex items-center gap-1.5 rounded-md bg-primary-soft px-4 py-2 text-sm font-bold text-primary hover:bg-teal-100 transition-colors cursor-pointer"
            >
              <Icon name="rotate-ccw" size={15} />
              Limpiar filtros
            </button>
          )}
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {items.map((tender) => (
            <TenderCard
              key={tender.id}
              tender={tender}
              isSaved={savedTenderIds.has(tender.id)}
              onToggleSave={toggleSave}
            />
          ))}

          {/* Pagination (HdU 07.4) */}
          <SearchPagination
            page={page}
            total={total}
            pageSize={pageSize}
            onPageChange={setPage}
          />
        </div>
      )}
    </section>
  );
}
