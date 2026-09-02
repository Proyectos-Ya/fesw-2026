"use client";

import React, { useState } from "react";
import { Icon } from "@/features/shared/components/Icon";
import {
  type AvailabilityFilter,
  AVAILABILITY_OPTIONS,
  SEARCH_REGIONS,
} from "../data/searchConstants";
import type { CommuneOption, ProvinceOption } from "../types";
import { useLocationCatalog } from "../hooks/useLocationCatalog";

interface SearchFiltersProps {
  regions: string[];
  onRegionsChange: (regions: string[]) => void;
  provinceId?: number;
  onProvinceChange?: (provinceId?: number) => void;
  communeId?: number;
  onCommuneChange?: (communeId?: number) => void;
  provinces?: ProvinceOption[];
  communes?: CommuneOption[];
  availability: AvailabilityFilter;
  onAvailabilityChange: (availability: AvailabilityFilter) => void;
  closingFrom?: string;
  closingTo?: string;
  onClosingDateRangeChange?: (from?: string, to?: string) => void;
  minAmount?: number;
  maxAmount?: number;
  onAmountRangeChange: (min?: number, max?: number) => void;
  onClearFilters: () => void;
  hasActiveFilters: boolean;
}

export function SearchFilters({
  regions,
  onRegionsChange,
  provinceId,
  onProvinceChange,
  communeId,
  onCommuneChange,
  provinces: customProvinces,
  communes: customCommunes,
  availability,
  onAvailabilityChange,
  closingFrom,
  closingTo,
  onClosingDateRangeChange,
  minAmount,
  maxAmount,
  onAmountRangeChange,
  onClearFilters,
  hasActiveFilters,
}: SearchFiltersProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [fromDate, setFromDate] = useState(closingFrom || "");
  const [toDate, setToDate] = useState(closingTo || "");
  const [minInput, setMinInput] = useState(minAmount !== undefined ? String(minAmount) : "");
  const [maxInput, setMaxInput] = useState(maxAmount !== undefined ? String(maxAmount) : "");

  const catalog = useLocationCatalog();
  const provinces = customProvinces ?? catalog.provinces;
  const communes = customCommunes ?? catalog.communes;

  const selectedRegion = regions.length === 1 ? regions[0] : null;
  const availableProvinces = selectedRegion
    ? provinces.filter((p) => p.region_name === selectedRegion)
    : [];
  const selectedProvince =
    availableProvinces.find((p) => p.id === provinceId) ?? null;
  const availableCommunes = selectedProvince
    ? communes.filter((c) => c.province_name === selectedProvince.name)
    : [];

  // Sync date inputs when props change
  React.useEffect(() => {
    setFromDate(closingFrom || "");
  }, [closingFrom]);

  React.useEffect(() => {
    setToDate(closingTo || "");
  }, [closingTo]);

  // Sync amount inputs when props change
  React.useEffect(() => {
    setMinInput(minAmount !== undefined ? String(minAmount) : "");
  }, [minAmount]);

  React.useEffect(() => {
    setMaxInput(maxAmount !== undefined ? String(maxAmount) : "");
  }, [maxAmount]);

  const handleRegionToggle = (region: string) => {
    let next: string[];
    if (regions.includes(region)) {
      next = regions.filter((r) => r !== region);
    } else {
      next = [...regions, region];
    }
    onRegionsChange(next);
    // Si la región cambia o se desmarca, resetea la provincia y la comuna seleccionadas
    if (provinceId !== undefined) {
      onProvinceChange?.(undefined);
    }
    if (communeId !== undefined) {
      onCommuneChange?.(undefined);
    }
  };

  const handleClearAllRegions = () => {
    onRegionsChange([]);
    if (provinceId !== undefined) {
      onProvinceChange?.(undefined);
    }
    if (communeId !== undefined) {
      onCommuneChange?.(undefined);
    }
  };

  const handleProvinceSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    const nextId = val ? parseInt(val, 10) : undefined;
    onProvinceChange?.(nextId);
    // Si la provincia cambia o se desmarca, resetea la comuna seleccionada
    if (communeId !== undefined) {
      onCommuneChange?.(undefined);
    }
  };

  const handleClearProvince = () => {
    onProvinceChange?.(undefined);
    if (communeId !== undefined) {
      onCommuneChange?.(undefined);
    }
  };

  const handleCommuneSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    const nextId = val ? parseInt(val, 10) : undefined;
    onCommuneChange?.(nextId);
  };

  const handleClearCommune = () => {
    onCommuneChange?.(undefined);
  };

  const handleAvailabilityToggle = (value: "vigentes" | "cerradas") => {
    if (availability === value) {
      onAvailabilityChange(null);
    } else {
      onAvailabilityChange(value);
    }
  };

  const handleApplyDates = (e: React.FormEvent) => {
    e.preventDefault();
    onClosingDateRangeChange?.(fromDate.trim() || undefined, toDate.trim() || undefined);
  };

  const handleClearDates = () => {
    setFromDate("");
    setToDate("");
    onClosingDateRangeChange?.(undefined, undefined);
  };

  const handleApplyBudget = (e: React.FormEvent) => {
    e.preventDefault();
    const parsedMin = minInput.trim() ? Number(minInput) : undefined;
    const parsedMax = maxInput.trim() ? Number(maxInput) : undefined;
    onAmountRangeChange(
      parsedMin !== undefined && !isNaN(parsedMin) ? parsedMin : undefined,
      parsedMax !== undefined && !isNaN(parsedMax) ? parsedMax : undefined,
    );
  };

  const activeFilterCount =
    regions.length +
    (provinceId !== undefined ? 1 : 0) +
    (communeId !== undefined ? 1 : 0) +
    (availability !== null ? 1 : 0) +
    (closingFrom ? 1 : 0) +
    (closingTo ? 1 : 0) +
    (minAmount !== undefined ? 1 : 0) +
    (maxAmount !== undefined ? 1 : 0);

  return (
    <div className="rounded-lg border border-border-subtle bg-surface-card shadow-xs transition-all">
      <div className="flex flex-wrap items-center justify-between gap-3 p-4">
        <button
          type="button"
          onClick={() => setIsOpen((prev) => !prev)}
          className="inline-flex items-center gap-2 text-sm font-bold text-text-strong hover:text-primary transition-colors cursor-pointer"
          aria-expanded={isOpen}
        >
          <Icon name="sliders-horizontal" size={18} color="var(--primary)" />
          <span>Filtros avanzados</span>
          {activeFilterCount > 0 && (
            <span className="flex size-5 items-center justify-center rounded-full bg-primary text-[11px] font-bold text-white">
              {activeFilterCount}
            </span>
          )}
          <Icon
            name={isOpen ? "chevron-up" : "chevron-down"}
            size={16}
            className="text-text-subtle ml-1"
          />
        </button>

        {hasActiveFilters && (
          <button
            type="button"
            onClick={onClearFilters}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-text-muted hover:text-danger transition-colors cursor-pointer"
          >
            <Icon name="x" size={14} />
            Limpiar todos los filtros
          </button>
        )}
      </div>

      {isOpen && (
        <div className="border-t border-border-subtle p-5 space-y-6 animate-in fade-in duration-200">
          {/* Regiones */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-bold uppercase tracking-caps text-text-subtle">
                Región ({regions.length > 0 ? `${regions.length} seleccionadas` : "Todas"})
              </label>
              {regions.length > 0 && (
                <button
                  type="button"
                  onClick={handleClearAllRegions}
                  className="text-xs text-primary hover:underline cursor-pointer"
                >
                  Deseleccionar todas
                </button>
              )}
            </div>
            <div className="flex flex-wrap gap-1.5 max-h-36 overflow-y-auto p-1 border border-border-subtle rounded-md bg-white">
              {SEARCH_REGIONS.map((region) => {
                const isSelected = regions.includes(region);
                return (
                  <button
                    key={region}
                    type="button"
                    onClick={() => handleRegionToggle(region)}
                    className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-medium transition-colors cursor-pointer ${
                      isSelected
                        ? "bg-primary-soft text-primary font-semibold border border-primary/30"
                        : "bg-surface-hover/70 text-text-muted hover:bg-warm-100 hover:text-text-strong border border-transparent"
                    }`}
                  >
                    {isSelected && <Icon name="check" size={12} />}
                    {region}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Ubicación en Cascada: Provincia y Comuna */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Selector de Provincia */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label
                  htmlFor="filter-province"
                  className="text-xs font-bold uppercase tracking-caps text-text-subtle"
                >
                  Provincia
                </label>
                {provinceId !== undefined && (
                  <button
                    type="button"
                    onClick={handleClearProvince}
                    className="text-xs text-primary hover:underline cursor-pointer"
                    aria-label="Limpiar provincia"
                  >
                    Limpiar
                  </button>
                )}
              </div>
              <select
                id="filter-province"
                aria-label="Provincia"
                value={provinceId ?? ""}
                onChange={handleProvinceSelect}
                disabled={!selectedRegion || availableProvinces.length === 0}
                className={`w-full rounded-md border border-border-subtle bg-white px-3 py-2 text-sm text-text-strong focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary ${
                  !selectedRegion
                    ? "opacity-60 bg-gray-50 cursor-not-allowed text-text-muted"
                    : "cursor-pointer"
                }`}
              >
                <option value="">
                  {!selectedRegion
                    ? regions.length > 1
                      ? "Selecciona solo una región primero"
                      : "Selecciona una región primero"
                    : "Todas las provincias"}
                </option>
                {availableProvinces.map((prov) => (
                  <option key={prov.id} value={prov.id}>
                    {prov.name}
                  </option>
                ))}
              </select>
              {!selectedRegion && (
                <p className="mt-1 text-[11px] text-text-muted">
                  {regions.length > 1
                    ? "Elige solo una región para filtrar por provincia y comuna."
                    : "Selecciona una región para habilitar las provincias."}
                </p>
              )}
            </div>

            {/* Selector de Comuna */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label
                  htmlFor="filter-commune"
                  className="text-xs font-bold uppercase tracking-caps text-text-subtle"
                >
                  Comuna
                </label>
                {communeId !== undefined && (
                  <button
                    type="button"
                    onClick={handleClearCommune}
                    className="text-xs text-primary hover:underline cursor-pointer"
                    aria-label="Limpiar comuna"
                  >
                    Limpiar
                  </button>
                )}
              </div>
              <select
                id="filter-commune"
                aria-label="Comuna"
                value={communeId ?? ""}
                onChange={handleCommuneSelect}
                disabled={!selectedProvince || availableCommunes.length === 0}
                className={`w-full rounded-md border border-border-subtle bg-white px-3 py-2 text-sm text-text-strong focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary ${
                  !selectedProvince
                    ? "opacity-60 bg-gray-50 cursor-not-allowed text-text-muted"
                    : "cursor-pointer"
                }`}
              >
                <option value="">
                  {!selectedRegion
                    ? "Selecciona una región primero"
                    : !selectedProvince
                      ? "Selecciona una provincia primero"
                      : "Todas las comunas"}
                </option>
                {availableCommunes.map((com) => (
                  <option key={com.id} value={com.id}>
                    {com.name}
                  </option>
                ))}
              </select>
              {selectedRegion && !selectedProvince && (
                <p className="mt-1 text-[11px] text-text-muted">
                  Selecciona una provincia para habilitar las comunas.
                </p>
              )}
            </div>
          </div>

          {/* Estado de postulación / Disponibilidad */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-caps text-text-subtle mb-2">
              Estado de postulación
            </label>
            <div className="flex flex-wrap gap-2">
              {AVAILABILITY_OPTIONS.map((option) => {
                const isSelected = availability === option.value;
                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => handleAvailabilityToggle(option.value)}
                    className={`inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-semibold transition-colors cursor-pointer border ${
                      isSelected
                        ? "bg-primary text-white border-primary shadow-xs"
                        : "bg-surface-card text-text-muted border-border-subtle hover:border-primary/50 hover:text-text-strong"
                    }`}
                  >
                    {isSelected && <Icon name="check" size={13} />}
                    {option.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Rango de Fechas (CA-1) */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-bold uppercase tracking-caps text-text-subtle">
                Fecha de cierre (Rango)
              </label>
              {(closingFrom || closingTo) && (
                <button
                  type="button"
                  onClick={handleClearDates}
                  className="text-xs text-primary hover:underline cursor-pointer"
                >
                  Limpiar fechas
                </button>
              )}
            </div>
            <form onSubmit={handleApplyDates} className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2 flex-1 min-w-[140px]">
                <span className="text-xs text-text-muted font-medium">Desde:</span>
                <input
                  type="date"
                  aria-label="Fecha de cierre desde"
                  value={fromDate}
                  onChange={(e) => setFromDate(e.target.value)}
                  className="w-full rounded-md border border-border-subtle bg-white px-3 py-1.5 text-sm text-text-strong focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>
              <div className="flex items-center gap-2 flex-1 min-w-[140px]">
                <span className="text-xs text-text-muted font-medium">Hasta:</span>
                <input
                  type="date"
                  aria-label="Fecha de cierre hasta"
                  value={toDate}
                  onChange={(e) => setToDate(e.target.value)}
                  className="w-full rounded-md border border-border-subtle bg-white px-3 py-1.5 text-sm text-text-strong focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>
              <button
                type="submit"
                className="inline-flex items-center gap-1 rounded-md bg-primary-soft px-3.5 py-1.5 text-xs font-bold text-primary hover:bg-teal-100 transition-colors cursor-pointer"
              >
                Aplicar fechas
              </button>
            </form>
          </div>

          {/* Rango de Monto CLP */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-caps text-text-subtle mb-2">
              Monto estimado (CLP)
            </label>
            <form onSubmit={handleApplyBudget} className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2 flex-1 min-w-[140px]">
                <span className="text-xs text-text-muted font-medium">Mín:</span>
                <input
                  type="number"
                  min="0"
                  step="10000"
                  placeholder="$ 0"
                  value={minInput}
                  onChange={(e) => setMinInput(e.target.value)}
                  className="w-full rounded-md border border-border-subtle bg-white px-3 py-1.5 text-sm text-text-strong placeholder:text-text-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>
              <div className="flex items-center gap-2 flex-1 min-w-[140px]">
                <span className="text-xs text-text-muted font-medium">Máx:</span>
                <input
                  type="number"
                  min="0"
                  step="10000"
                  placeholder="$ Sin límite"
                  value={maxInput}
                  onChange={(e) => setMaxInput(e.target.value)}
                  className="w-full rounded-md border border-border-subtle bg-white px-3 py-1.5 text-sm text-text-strong placeholder:text-text-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>
              <button
                type="submit"
                className="inline-flex items-center gap-1 rounded-md bg-primary-soft px-3.5 py-1.5 text-xs font-bold text-primary hover:bg-teal-100 transition-colors cursor-pointer"
              >
                Aplicar montos
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
