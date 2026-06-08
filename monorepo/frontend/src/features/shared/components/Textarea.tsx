import React from "react";

interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string;
  error?: string;
  hint?: string;
  charCount?: number;
  maxChars?: number;
}

export function Textarea({
  label,
  error,
  hint,
  charCount,
  maxChars,
  id,
  className = "",
  ...rest
}: TextareaProps) {
  const textareaId = id ?? `ta-${label.toLowerCase().replace(/\s+/g, "-")}`;
  const over =
    charCount !== undefined && maxChars !== undefined && charCount > maxChars;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={textareaId} className="text-sm font-semibold text-zinc-900">
        {label}
      </label>
      <textarea
        id={textareaId}
        rows={5}
        className={`w-full resize-none rounded-input border px-3.5 py-2.5 text-sm text-zinc-900 placeholder:text-zinc-400 transition-colors focus:outline-none focus:ring-2 focus:ring-brand-primary-500 focus:border-brand-primary-500 ${
          error
            ? "border-semantic-danger-base bg-semantic-danger-light"
            : "border-zinc-200 bg-white hover:border-zinc-400"
        } ${className}`}
        {...rest}
      />
      <div className="flex items-start justify-between">
        {error ? (
          <p className="text-xs text-semantic-danger-base">{error}</p>
        ) : hint ? (
          <p className="text-xs text-zinc-400">{hint}</p>
        ) : (
          <span />
        )}
        {maxChars !== undefined && charCount !== undefined ? (
          <p
            className={`ml-auto text-xs ${
              over ? "text-semantic-danger-base" : "text-zinc-400"
            }`}
          >
            {charCount}/{maxChars}
          </p>
        ) : null}
      </div>
    </div>
  );
}
