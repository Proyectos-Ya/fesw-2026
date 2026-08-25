"use client";

import type { ChangeEvent } from "react";
import { Icon } from "@/features/shared/components/Icon";
import { isBudgetFilterActive, type BudgetRange } from "../utils/filter";
import { LocationFilter } from "./LocationFilter";

interface BudgetFilterProps {
  value: BudgetRange;
  onChange: (next: BudgetRange) => void;
  regions: string[];
  region: string | null;
  onRegionChange: (next: string | null) => void;
  provinces: string[];
  province: string | null;
  onProvinceChange: (next: string | null) => void;
  communes: string[];
  commune: string | null;
  onCommuneChange: (next: string | null) => void;
}

function parseAmount(raw: string): number | null {
  const trimmed = raw.trim();
  if (trimmed === "") return null;
  const n = Number(trimmed);
  if (!Number.isFinite(n) || n < 0) return null;
  return n;
}

function BudgetInput({
  label,
  id,
  placeholder,
  value,
  onChange,
}: {
  label: string;
  id: string;
  placeholder: string;
  value: number | null;
  onChange: (next: number | null) => void;
}) {
  const handle = (e: ChangeEvent<HTMLInputElement>) => onChange(parseAmount(e.target.value));
  return (
    <div className="flex min-w-0 flex-1 flex-col gap-1">
      <label
        htmlFor={id}
        className="text-[10px] font-bold uppercase tracking-caps text-text-subtle"
      >
        {label}
      </label>
      <div className="flex items-center rounded-md border border-border-default bg-white px-3 py-2 focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/15 transition-all">
        <span className="font-mono text-sm text-text-subtle">$</span>
        <input
          id={id}
          type="number"
          inputMode="numeric"
          min={0}
          step={100000}
          placeholder={placeholder}
          value={value ?? ""}
          onChange={handle}
          className="ml-1.5 w-full bg-transparent font-mono text-sm text-text-strong placeholder:text-text-subtle outline-none [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
        />
      </div>
    </div>
  );
}

export function BudgetFilter({
  value,
  onChange,
  regions,
  region,
  onRegionChange,
  provinces,
  province,
  onProvinceChange,
  communes,
  commune,
  onCommuneChange,
}: BudgetFilterProps) {
  const active = isBudgetFilterActive(value) || region !== null || province !== null || commune !== null;

  return (
    <div className="mb-5 flex flex-wrap items-end gap-3 rounded-lg border border-border-subtle bg-surface-card p-4 shadow-xs sm:flex-nowrap">
      <div className="inline-flex shrink-0 items-center self-end pb-2.5 pr-1">
        <Icon name="sliders-horizontal" size={16} color="var(--primary)" />
      </div>
      <LocationFilter
        regions={regions}
        region={region}
        onRegionChange={onRegionChange}
        provinces={provinces}
        province={province}
        onProvinceChange={onProvinceChange}
        communes={communes}
        commune={commune}
        onCommuneChange={onCommuneChange}
      />
      <BudgetInput
        label="Desde"
        id="budget-min"
        placeholder="Sin mínimo"
        value={value.min}
        onChange={(min) => onChange({ ...value, min })}
      />
      <BudgetInput
        label="Hasta"
        id="budget-max"
        placeholder="Sin tope"
        value={value.max}
        onChange={(max) => onChange({ ...value, max })}
      />
      {active && (
        <button
          type="button"
          onClick={() => {
            onChange({ min: null, max: null });
            onRegionChange(null);
            onProvinceChange(null);
            onCommuneChange(null);
          }}
          className="inline-flex shrink-0 items-center gap-1.5 self-end px-2 py-2 text-xs font-bold text-text-muted hover:text-primary transition-colors"
        >
          <Icon name="x" size={14} />
          Limpiar
        </button>
      )}
    </div>
  );
}
