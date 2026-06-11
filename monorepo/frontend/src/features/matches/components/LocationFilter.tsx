"use client";

import type { ChangeEvent } from "react";
import { Icon } from "@/features/shared/components/Icon";

interface LocationFilterProps {
  /** Regiones disponibles según los matches cargados. */
  regions: string[];
  value: string | null;
  onChange: (next: string | null) => void;
}

export function LocationFilter({ regions, value, onChange }: LocationFilterProps) {
  const handle = (e: ChangeEvent<HTMLSelectElement>) =>
    onChange(e.target.value === "" ? null : e.target.value);

  return (
    <div className="flex w-full flex-col gap-1">
      <label
        htmlFor="location-region"
        className="text-[10px] font-bold uppercase tracking-caps text-text-subtle"
      >
        Ubicación
      </label>
      <div className="flex min-w-0 items-center rounded-md border border-border-default bg-white px-3 py-2 focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/15 transition-all">
        <Icon name="map-pin" size={15} color="var(--text-subtle)" />
        <select
          id="location-region"
          value={value ?? ""}
          onChange={handle}
          className="ml-1.5 w-full min-w-0 truncate bg-transparent text-sm text-text-strong outline-none"
        >
          <option value="">Todas las regiones</option>
          {regions.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
