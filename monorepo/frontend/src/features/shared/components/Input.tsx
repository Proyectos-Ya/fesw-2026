import React from "react";

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  hint?: string;
}

export function Input({ label, error, hint, id, className = "", ...rest }: InputProps) {
  const inputId = id ?? `input-${label.toLowerCase().replace(/\s+/g, "-")}`;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={inputId} className="text-sm font-semibold text-text-strong">
        {label}
      </label>
      <input
        id={inputId}
        className={`w-full rounded-md border px-3.5 py-2.5 text-sm text-text-body placeholder:text-text-subtle transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary ${
          error
            ? "border-danger bg-danger-soft/30"
            : "border-border-default bg-white hover:border-border-strong"
        } ${className}`}
        {...rest}
      />
      {error ? (
        <p className="text-xs text-danger">{error}</p>
      ) : hint ? (
        <p className="text-xs text-text-muted">{hint}</p>
      ) : null}
    </div>
  );
}
