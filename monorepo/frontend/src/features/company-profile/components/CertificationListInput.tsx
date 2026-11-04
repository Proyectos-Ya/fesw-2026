"use client";

import { useId, useState, type KeyboardEvent } from "react";
import { Input } from "@/features/shared/components/Input";
import { Button } from "@/features/shared/components/Button";
import {
  formatCertificationDate,
  normalizeCertification,
  type CertificationEntry,
  type CertificationItem,
} from "../profileSchema";
import {
  certificationKey,
  cleanCertificationName,
  getCertificationStatus,
} from "../utils/certification";

interface CertificationListInputProps {
  label: string;
  value: CertificationEntry[];
  onChange: (value: CertificationItem[]) => void;
  hint?: string;
  error?: string;
  optional?: boolean;
}

export function CertificationListInput({
  label,
  value,
  onChange,
  hint,
  error,
  optional = false,
}: CertificationListInputProps) {
  const id = useId();
  const [name, setName] = useState("");
  const [expiresAt, setExpiresAt] = useState("");

  const items = value.map(normalizeCertification);

  const add = () => {
    const cleaned = cleanCertificationName(name);
    if (!cleaned) return;
    const key = certificationKey(cleaned);
    const exists = items.some((item) => certificationKey(item.name) === key);
    if (!exists) {
      onChange([...items, { name: cleaned, expires_at: expiresAt || null }]);
    }
    setName("");
    setExpiresAt("");
  };

  const remove = (index: number) => onChange(items.filter((_, i) => i !== index));

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      add();
    }
  };

  return (
    <div className="flex flex-col gap-3" role="group" aria-labelledby={`${id}-label`}>
      <span id={`${id}-label`} className="text-sm font-semibold text-text-strong">
        {label}{" "}
        {optional ? <span className="font-normal text-text-subtle">(opcional)</span> : null}
      </span>

      <div className="grid grid-cols-1 items-end gap-3 sm:grid-cols-[1fr_auto_auto]">
        <Input
          id={`${id}-name`}
          label="Nombre de la certificación"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ej: ISO 9001, OHSAS 18001, SEC..."
        />
        <Input
          id={`${id}-date`}
          type="date"
          label="Fecha de vencimiento"
          value={expiresAt}
          onChange={(e) => setExpiresAt(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <Button type="button" variant="primary" onClick={add}>
          Agregar
        </Button>
      </div>

      {items.length > 0 && (
        <ul className="flex flex-col gap-2">
          {items.map((item, index) => (
            <li
              key={`${item.name}-${index}`}
              className="flex items-center justify-between gap-3 rounded-md border border-border-subtle bg-surface-card px-3 py-2"
            >
              <div className="flex min-w-0 flex-col">
                <span className="text-sm font-medium text-text-strong break-words">
                  {item.name}
                </span>
                {item.expires_at ? (
                  <span className="text-xs text-text-muted">
                    Vence: {formatCertificationDate(item.expires_at)}
                  </span>
                ) : null}
                {getCertificationStatus(item.expires_at).status === "expired" ? (
                  <span className="text-xs font-medium text-danger">
                    Esta certificación ya está vencida.
                  </span>
                ) : null}
              </div>
              <button
                type="button"
                onClick={() => remove(index)}
                className="text-lg leading-none text-text-muted hover:text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
                aria-label={`Eliminar ${item.name}`}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}

      {error ? (
        <p className="text-xs text-danger">{error}</p>
      ) : hint ? (
        <p className="text-xs text-text-muted">{hint}</p>
      ) : null}
    </div>
  );
}
