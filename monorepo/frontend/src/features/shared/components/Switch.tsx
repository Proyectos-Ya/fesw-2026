"use client";

import { useId } from "react";

interface SwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
  description?: string;
  disabled?: boolean;
  id?: string;
  className?: string;
}

/**
 * Interruptor de encendido/apagado.
 *
 * Portado desde `templates/components/forms/Switch.jsx` a Tailwind. El input
 * real sigue en el DOM (solo visualmente oculto, no `display:none`) para que el
 * teclado y los lectores de pantalla lo encuentren; lo que se ve es la pista y
 * el círculo.
 */
export function Switch({
  checked,
  onChange,
  label,
  description,
  disabled = false,
  id,
  className = "",
}: SwitchProps) {
  const autoId = useId();
  const fieldId = id ?? autoId;

  return (
    <label
      htmlFor={fieldId}
      className={`inline-flex items-start gap-3 ${
        disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer"
      } ${className}`}
    >
      <input
        id={fieldId}
        type="checkbox"
        role="switch"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        className="sr-only peer"
      />
      <span
        aria-hidden="true"
        className={`relative mt-0.5 h-6 w-10 flex-none rounded-full transition-colors duration-200 peer-focus-visible:ring-2 peer-focus-visible:ring-primary peer-focus-visible:ring-offset-2 ${
          checked ? "bg-primary" : "bg-warm-300"
        }`}
      >
        <span
          className={`absolute top-[3px] size-[18px] rounded-full bg-white shadow-xs transition-[left] duration-200 ${
            checked ? "left-[19px]" : "left-[3px]"
          }`}
        />
      </span>
      {(label || description) && (
        <span className="flex flex-col gap-0.5">
          {label && (
            <span className="text-sm font-semibold text-text-strong">{label}</span>
          )}
          {description && (
            <span className="text-xs text-text-subtle">{description}</span>
          )}
        </span>
      )}
    </label>
  );
}
