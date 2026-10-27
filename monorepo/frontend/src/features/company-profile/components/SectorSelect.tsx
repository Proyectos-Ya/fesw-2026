"use client";

import { useState } from "react";
import { ChipSelect } from "@/features/shared/components/ChipSelect";
import { Input } from "@/features/shared/components/Input";
import { SECTOR_GROUPS } from "../data/sectors";

interface SectorSelectProps {
  selected: string[];
  onChange: (selected: string[]) => void;
  label?: string;
  error?: string;
}

function normalize(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .trim();
}

/**
 * Picks Mercado Público sectors grouped by type, with a text filter.
 * Every group's ChipSelect gets the full selection, so choosing in one group keeps
 * what was chosen in the others and onChange returns sectors in the order picked.
 * Selected sectors stay visible even when the filter excludes them.
 */
export function SectorSelect({
  selected,
  onChange,
  label = "Rubros principales",
  error,
}: SectorSelectProps) {
  const [query, setQuery] = useState("");
  const needle = normalize(query);

  const groups = SECTOR_GROUPS.map((group) => ({
    title: group.title,
    options: group.sectors.filter(
      (sector) => selected.includes(sector) || normalize(sector).includes(needle),
    ),
  })).filter((group) => group.options.length > 0);

  return (
    <div className="flex flex-col gap-4">
      <Input
        label={label}
        id="sector-search"
        type="search"
        placeholder="Buscar rubro"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      {groups.map((group) => (
        <ChipSelect
          key={group.title}
          label={group.title}
          options={group.options}
          selected={selected}
          onChange={onChange}
        />
      ))}
      {groups.length === 0 ? (
        <p className="text-sm text-text-muted">Ningún rubro coincide con la búsqueda.</p>
      ) : null}
      {error ? <p className="text-xs text-danger">{error}</p> : null}
    </div>
  );
}
