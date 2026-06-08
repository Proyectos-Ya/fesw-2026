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
      <label className="text-sm font-semibold text-zinc-900">
        {label}{" "}
        {optional ? (
          <span className="font-normal text-zinc-400">(opcional)</span>
        ) : null}
      </label>
      <div
        className={`flex flex-wrap gap-2 rounded-input border bg-white px-3 py-2 transition-colors focus-within:border-brand-primary-500 focus-within:ring-2 focus-within:ring-brand-primary-500 ${
          error ? "border-semantic-danger-base" : "border-zinc-200"
        }`}
      >
        {tags.map((tag) => (
          <span
            key={tag}
            className="inline-flex items-center gap-1 rounded-full bg-brand-primary-100 px-2.5 py-0.5 text-xs font-medium text-brand-primary-900"
          >
            {tag}
            <button
              type="button"
              onClick={() => remove(tag)}
              className="ml-0.5 hover:text-brand-primary-700 focus:outline-none"
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
          className="min-w-[120px] flex-1 bg-transparent text-sm outline-none placeholder:text-zinc-400"
        />
      </div>
      {error ? (
        <p className="text-xs text-semantic-danger-base">{error}</p>
      ) : hint ? (
        <p className="text-xs text-zinc-400">{hint}</p>
      ) : null}
    </div>
  );
}
