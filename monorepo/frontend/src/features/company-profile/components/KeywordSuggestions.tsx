"use client";

import { Sparkles } from "lucide-react";

interface KeywordSuggestionsProps {
  suggestions: string[];
  /** Palabras clave que el usuario ya tiene; no se vuelven a sugerir. */
  selected: string[];
  onAdd: (keywords: string[]) => void;
}

const normalize = (keyword: string) => keyword.trim().toLocaleLowerCase("es");

/** Palabras clave importadas desde el RUT, que el usuario agrega con un clic. */
export function KeywordSuggestions({ suggestions, selected, onAdd }: KeywordSuggestionsProps) {
  const taken = new Set(selected.map(normalize));
  const pending = suggestions.filter((keyword) => !taken.has(normalize(keyword)));

  if (pending.length === 0) return null;

  return (
    <div className="flex flex-col gap-2.5 rounded-md border border-dashed border-primary-border bg-primary-soft/30 px-3 py-3">
      <div className="flex items-center justify-between gap-3">
        <span className="eyebrow flex items-center gap-1.5">
          <Sparkles className="size-3.5" aria-hidden="true" />
          Sugeridas para tu empresa
        </span>
        <button
          type="button"
          onClick={() => onAdd(pending)}
          className="rounded-xs text-xs font-semibold text-primary transition-colors hover:text-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
        >
          Agregar todas
        </button>
      </div>
      <div className="flex flex-wrap gap-2">
        {pending.map((keyword) => (
          <button
            key={keyword}
            type="button"
            onClick={() => onAdd([keyword])}
            aria-label={`Agregar ${keyword}`}
            className="inline-flex items-center gap-1 rounded-full border border-dashed border-primary-border bg-white px-2.5 py-0.5 text-xs font-medium text-primary transition-all duration-200 hover:border-primary hover:bg-primary-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
          >
            <span aria-hidden="true">+</span>
            {keyword}
          </button>
        ))}
      </div>
      <p className="text-xs text-text-muted">
        Salen de tus actividades económicas en el SII. Agrega solo las que describan lo que
        realmente haces.
      </p>
    </div>
  );
}
