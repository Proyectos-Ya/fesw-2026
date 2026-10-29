"use client";

import { Sparkles, X } from "lucide-react";

interface KeywordSuggestionsProps {
  suggestions: string[];
  /** Palabras clave que el usuario ya tiene; no se vuelven a sugerir. */
  selected: string[];
  /** Sugerencias que el usuario descartó; no se muestran ni entran en "Agregar todas". */
  dismissed?: string[];
  onAdd: (keywords: string[]) => void;
  /** Si no se pasa, los chips no tienen botón de descarte. */
  onDismiss?: (keyword: string) => void;
  /** Texto al pie; por omisión explica que vienen de las actividades del SII. */
  hint?: string;
}

const SII_HINT =
  "Salen de tus actividades económicas en el SII. Agrega solo las que describan lo que realmente haces.";

const normalize = (keyword: string) => keyword.trim().toLocaleLowerCase("es");

/** Palabras clave sugeridas que el usuario agrega o descarta con un clic. */
export function KeywordSuggestions({
  suggestions,
  selected,
  dismissed = [],
  onAdd,
  onDismiss,
  hint = SII_HINT,
}: KeywordSuggestionsProps) {
  const hidden = new Set([...selected, ...dismissed].map(normalize));
  const pending = suggestions.filter((keyword) => !hidden.has(normalize(keyword)));

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
          <span
            key={keyword}
            className="inline-flex items-center rounded-full border border-dashed border-primary-border bg-white text-xs font-medium text-primary transition-all duration-200 focus-within:ring-2 focus-within:ring-primary/30 hover:border-primary hover:bg-primary-soft"
          >
            <button
              type="button"
              onClick={() => onAdd([keyword])}
              aria-label={`Agregar ${keyword}`}
              className={`inline-flex items-center gap-1 rounded-full py-0.5 pl-2.5 focus-visible:outline-none ${
                onDismiss ? "pr-1.5" : "pr-2.5"
              }`}
            >
              <span aria-hidden="true">+</span>
              {keyword}
            </button>
            {onDismiss && (
              <button
                type="button"
                onClick={() => onDismiss(keyword)}
                aria-label={`Descartar ${keyword}`}
                className="mr-1 rounded-full p-0.5 text-text-muted transition-colors hover:text-danger focus-visible:outline-none"
              >
                <X className="size-3" aria-hidden="true" />
              </button>
            )}
          </span>
        ))}
      </div>
      <p className="text-xs text-text-muted">{hint}</p>
    </div>
  );
}
