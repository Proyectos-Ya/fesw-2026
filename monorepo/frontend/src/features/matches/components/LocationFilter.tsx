"use client";

import type { ChangeEvent } from "react";
import { Icon } from "@/features/shared/components/Icon";

interface LocationFilterProps {
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

function LocationSelect({
  id,
  label,
  placeholder,
  options,
  value,
  onChange,
  disabled,
}: {
  id: string;
  label: string;
  placeholder: string;
  options: string[];
  value: string | null;
  onChange: (next: string | null) => void;
  disabled?: boolean;
}) {
  const handle = (e: ChangeEvent<HTMLSelectElement>) =>
    onChange(e.target.value === "" ? null : e.target.value);

  return (
    <div className="flex min-w-0 flex-1 flex-col gap-1">
      <label
        htmlFor={id}
        className="text-[10px] font-bold uppercase tracking-caps text-text-subtle"
      >
        {label}
      </label>
      <div
        className={[
          "flex min-w-0 items-center rounded-md border bg-white px-3 py-2 transition-all",
          disabled
            ? "border-border-subtle opacity-50 cursor-not-allowed"
            : "border-border-default focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/15",
        ].join(" ")}
      >
        <Icon name="map-pin" size={15} color="var(--text-subtle)" />
        <select
          id={id}
          value={value ?? ""}
          onChange={handle}
          disabled={disabled}
          className="ml-1.5 w-full min-w-0 truncate bg-transparent text-sm text-text-strong outline-none disabled:cursor-not-allowed"
        >
          <option value="">{placeholder}</option>
          {options.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

export function LocationFilter({
  regions,
  region,
  onRegionChange,
  provinces,
  province,
  onProvinceChange,
  communes,
  commune,
  onCommuneChange,
}: LocationFilterProps) {
  return (
    <>
      <LocationSelect
        id="location-region"
        label="Región"
        placeholder="Todas las regiones"
        options={regions}
        value={region}
        onChange={onRegionChange}
      />
      <LocationSelect
        id="location-province"
        label="Provincia"
        placeholder={region ? "Todas las provincias" : "Selecciona región primero"}
        options={provinces}
        value={province}
        onChange={onProvinceChange}
        disabled={!region}
      />
      <LocationSelect
        id="location-commune"
        label="Comuna"
        placeholder={province ? "Todas las comunas" : "Selecciona provincia primero"}
        options={communes}
        value={commune}
        onChange={onCommuneChange}
        disabled={!province}
      />
    </>
  );
}
