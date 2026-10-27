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

function selectedLabel(count: number): string {
  return count === 1 ? "1 elegido" : `${count} elegidos`;
}

/**
 * Picks Mercado Público sectors grouped by type, with a text filter.
 * Groups start collapsed and their header shows how many sectors they hold and how
 * many are selected. While searching, every group with a match opens on its own;
 * clearing the search goes back to the groups the user opened.
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
  const [openGroups, setOpenGroups] = useState<ReadonlySet<string>>(new Set());
  const needle = normalize(query);
  const searching = needle.length > 0;

  const toggleGroup = (title: string) => {
    setOpenGroups((current) => {
      const next = new Set(current);
      if (next.has(title)) {
        next.delete(title);
      } else {
        next.add(title);
      }
      return next;
    });
  };

  const groups = SECTOR_GROUPS.map((group) => ({
    title: group.title,
    total: group.sectors.length,
    selectedCount: group.sectors.filter((sector) => selected.includes(sector)).length,
    options: group.sectors.filter(
      (sector) => selected.includes(sector) || normalize(sector).includes(needle),
    ),
  })).filter((group) => !searching || group.options.length > 0);

  return (
    <div className="flex flex-col gap-3">
      <Input
        label={label}
        id="sector-search"
        type="search"
        placeholder="Buscar rubro"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      <div className="flex flex-col divide-y divide-border-default rounded-lg border border-border-default">
        {groups.map((group) => {
          const expanded = searching || openGroups.has(group.title);
          const panelId = `sector-group-${normalize(group.title).replace(/\s+/g, "-")}`;
          return (
            <div key={group.title} className="flex flex-col">
              <button
                type="button"
                aria-expanded={expanded}
                aria-controls={panelId}
                onClick={() => toggleGroup(group.title)}
                disabled={searching}
                className="flex items-center justify-between gap-3 px-4 py-3 text-left transition-colors hover:bg-bg-page focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 disabled:cursor-default disabled:hover:bg-transparent"
              >
                <span className="flex items-center gap-2 text-sm font-semibold text-text-strong">
                  <span aria-hidden="true" className="text-text-muted">
                    {expanded ? "▾" : "▸"}
                  </span>
                  {group.title}
                  <span className="font-normal text-text-muted">({group.total})</span>
                </span>
                <span
                  className={`text-xs ${group.selectedCount > 0 ? "font-semibold text-primary" : "text-text-muted"}`}
                >
                  {selectedLabel(group.selectedCount)}
                </span>
              </button>
              {expanded ? (
                <div id={panelId} className="px-4 pb-4">
                  <ChipSelect
                    label=""
                    options={group.options}
                    selected={selected}
                    onChange={onChange}
                  />
                </div>
              ) : null}
            </div>
          );
        })}
        {groups.length === 0 ? (
          <p className="px-4 py-3 text-sm text-text-muted">
            Ningún rubro coincide con la búsqueda.
          </p>
        ) : null}
      </div>
      {error ? <p className="text-xs text-danger">{error}</p> : null}
    </div>
  );
}
