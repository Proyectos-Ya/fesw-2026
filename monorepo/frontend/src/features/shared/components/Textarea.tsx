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
      <label htmlFor={textareaId} className="text-sm font-semibold text-text-strong">
        {label}
      </label>
      <textarea
        id={textareaId}
        rows={5}
        className={`w-full resize-none rounded-md border px-3.5 py-2.5 text-sm text-text-body placeholder:text-text-subtle transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary ${
          error
            ? "border-danger bg-danger-soft/30"
            : "border-border-default bg-white hover:border-border-strong"
        } ${className}`}
        {...rest}
      />
      <div className="flex items-start justify-between">
        {error ? (
          <p className="text-xs text-danger">{error}</p>
        ) : hint ? (
          <p className="text-xs text-text-muted">{hint}</p>
        ) : (
          <span />
        )}
        {maxChars !== undefined && charCount !== undefined ? (
          <p
            className={`ml-auto text-xs ${
              over ? "text-danger" : "text-text-muted"
            }`}
          >
            {charCount}/{maxChars}
          </p>
        ) : null}
      </div>
    </div>
  );
}
