"use client";

import type { ChangeEvent } from "react";
import { Icon } from "@/features/shared/components/Icon";

interface LocationFilterProps {
  /** Provincias disponibles según los matches cargados. */
  provinces: string[];
  value: string | null;
  onChange: (next: string | null) => void;
}

export function LocationFilter({ provinces, value, onChange }: LocationFilterProps) {
  const handle = (e: ChangeEvent<HTMLSelectElement>) =>
    onChange(e.target.value === "" ? null : e.target.value);

  return (
    <div className="flex flex-col gap-1">
      <label
        htmlFor="location-province"
        className="text-[10px] font-bold uppercase tracking-caps text-text-subtle"
      >
        Ubicación
      </label>
      <div className="flex items-center rounded-md border border-border-default bg-white px-3 py-2 focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/15 transition-all">
        <Icon name="map-pin" size={15} color="var(--text-subtle)" />
        <select
          id="location-province"
          value={value ?? ""}
          onChange={handle}
          className="ml-1.5 w-full bg-transparent text-sm text-text-strong outline-none"
        >
          <option value="">Todas las provincias</option>
          {provinces.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
