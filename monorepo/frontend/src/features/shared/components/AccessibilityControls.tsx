"use client";

import { Moon, Sun } from "lucide-react";
import {
  usePreferences,
  type FontScale,
} from "@/features/shared/context/PreferencesContext";

interface AccessibilityControlsProps {
  compact?: boolean;
  className?: string;
}

const FONT_SCALE_OPTIONS: ReadonlyArray<{
  scale: FontScale;
  shortLabel: string;
  ariaLabel: string;
}> = [
  {
    scale: "normal",
    shortLabel: "A",
    ariaLabel: "Tamaño de letra normal",
  },
  {
    scale: "large",
    shortLabel: "A+",
    ariaLabel: "Tamaño de letra grande",
  },
  {
    scale: "xlarge",
    shortLabel: "A++",
    ariaLabel: "Tamaño de letra extra grande",
  },
];

export function AccessibilityControls({
  compact = false,
  className = "",
}: AccessibilityControlsProps) {
  const { theme, toggleTheme, fontScale, setFontScale } = usePreferences();
  const isDark = theme === "dark";

  return (
    <div
      className={`flex items-center justify-between gap-2 ${className}`.trim()}
      aria-label="Controles de accesibilidad y apariencia"
    >
      <button
        type="button"
        onClick={toggleTheme}
        aria-label={isDark ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
        aria-pressed={isDark}
        data-testid="theme-toggle"
        title={isDark ? "Modo claro" : "Modo oscuro"}
        className="inline-flex items-center gap-2 rounded-lg border border-border-subtle bg-surface-inset px-2.5 py-1.5 text-xs font-semibold text-text-body transition-colors hover:bg-surface-hover hover:text-text-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      >
        {isDark ? (
          <Sun className="h-4 w-4 text-accent" aria-hidden="true" />
        ) : (
          <Moon className="h-4 w-4 text-text-muted" aria-hidden="true" />
        )}
        {!compact && <span>{isDark ? "Claro" : "Oscuro"}</span>}
      </button>

      <div
        role="group"
        aria-label="Tamaño de fuente"
        className="inline-flex items-center rounded-lg border border-border-subtle bg-surface-inset p-0.5"
      >
        {FONT_SCALE_OPTIONS.map((option) => {
          const isActive = fontScale === option.scale;
          return (
            <button
              key={option.scale}
              type="button"
              onClick={() => setFontScale(option.scale)}
              aria-label={option.ariaLabel}
              aria-pressed={isActive}
              data-testid={`font-scale-${option.scale}`}
              title={option.ariaLabel}
              className={`rounded-md px-2 py-1 text-xs font-bold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
                isActive
                  ? "bg-primary text-on-primary shadow-xs"
                  : "text-text-muted hover:bg-surface-hover hover:text-text-strong"
              }`}
            >
              {option.shortLabel}
            </button>
          );
        })}
      </div>
    </div>
  );
}
