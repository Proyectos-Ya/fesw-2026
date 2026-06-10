"use client";

interface ChipSelectProps {
  label: string;
  options: readonly string[];
  selected: string[];
  onChange: (selected: string[]) => void;
  error?: string;
  hint?: string;
}

export function ChipSelect({
  label,
  options,
  selected,
  onChange,
  error,
  hint,
}: ChipSelectProps) {
  const toggle = (option: string) => {
    if (selected.includes(option)) {
      onChange(selected.filter((s) => s !== option));
    } else {
      onChange([...selected, option]);
    }
  };
  return (
    <div className="flex flex-col gap-2">
      <span className="text-sm font-semibold text-text-strong">{label}</span>
      <div className="flex flex-wrap gap-2">
        {options.map((option) => {
          const isSelected = selected.includes(option);
          return (
            <button
              key={option}
              type="button"
              onClick={() => toggle(option)}
              aria-pressed={isSelected}
              className={`rounded-full border px-4 py-1.5 text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 ${
                isSelected
                  ? "border-primary bg-primary-soft text-primary shadow-sm"
                  : "border-border-default bg-white text-text-muted hover:border-border-strong hover:bg-bg-page"
              }`}
            >
              {option}
            </button>
          );
        })}
      </div>
      {error ? (
        <p className="text-xs text-danger">{error}</p>
      ) : hint ? (
        <p className="text-xs text-text-muted">{hint}</p>
      ) : null}
    </div>
  );
}
