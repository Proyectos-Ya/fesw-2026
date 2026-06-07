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
      <label htmlFor={inputId} className="text-sm font-semibold text-zinc-900">
        {label}
      </label>
      <input
        id={inputId}
        className={`w-full rounded-input border px-3.5 py-2.5 text-sm text-zinc-900 placeholder:text-zinc-400 transition-colors focus:outline-none focus:ring-2 focus:ring-brand-primary-500 focus:border-brand-primary-500 ${
          error
            ? "border-semantic-danger-base bg-semantic-danger-light"
            : "border-zinc-200 bg-white hover:border-zinc-400"
        } ${className}`}
        {...rest}
      />
      {error ? (
        <p className="text-xs text-semantic-danger-base">{error}</p>
      ) : hint ? (
        <p className="text-xs text-zinc-400">{hint}</p>
      ) : null}
    </div>
  );
}
