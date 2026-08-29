"use client";

import { useState, type KeyboardEvent } from "react";

interface TagInputProps {
  label: string;
  tags: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
  hint?: string;
  error?: string;
  optional?: boolean;
}

export function TagInput({
  label,
  tags,
  onChange,
  placeholder = "Escribe y presiona Enter...",
  hint,
  error,
  optional = false,
}: TagInputProps) {
  const [value, setValue] = useState("");

  const add = (raw: string) => {
    const trimmed = raw.trim().replace(/,$/, "").trim();
    if (trimmed && !tags.includes(trimmed)) {
      onChange([...tags, trimmed]);
    }
    setValue("");
  };

  const remove = (tag: string) => onChange(tags.filter((t) => t !== tag));

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      add(value);
    } else if (e.key === "Backspace" && value === "" && tags.length > 0) {
      onChange(tags.slice(0, -1));
    }
  };

  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-sm font-semibold text-text-strong">
        {label}{" "}
        {optional ? (
          <span className="font-normal text-text-subtle">(opcional)</span>
        ) : null}
      </label>
      <div
        className={`flex flex-wrap gap-2 rounded-md border bg-white px-3 py-2 transition-all duration-200 focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20 ${
          error ? "border-danger" : "border-border-default hover:border-border-strong"
        }`}
      >
        {tags.map((tag) => (
          <span
            key={tag}
            className="inline-flex items-center gap-1 rounded-full bg-primary-soft px-2.5 py-0.5 text-xs font-medium text-primary shadow-sm"
          >
            {tag}
            <button
              type="button"
              onClick={() => remove(tag)}
              className="ml-0.5 hover:text-primary-hover focus:outline-none"
              aria-label={`Eliminar ${tag}`}
            >
              ×
            </button>
          </span>
        ))}
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={() => {
            if (value) add(value);
          }}
          placeholder={tags.length === 0 ? placeholder : ""}
          className="min-w-[120px] flex-1 bg-transparent text-sm outline-none text-text-body placeholder:text-text-subtle"
        />
      </div>
      {error ? (
        <p className="text-xs text-danger">{error}</p>
      ) : hint ? (
        <p className="text-xs text-text-muted">{hint}</p>
      ) : null}
    </div>
  );
}
