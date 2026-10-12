"use client";

import { useEffect, useRef, useState } from "react";

import { Button } from "@/features/shared/components/Button";
import { Icon } from "@/features/shared/components/Icon";
import { Switch } from "@/features/shared/components/Switch";

import { EXPORT_SECTIONS, EXPORT_SECTION_LABELS, type ExportSection } from "../types";

interface ExcelExportDialogProps {
  open: boolean;
  onConfirm: (sections: ExportSection[]) => void;
  onClose: () => void;
}

/** Elegir qué va en el Excel antes de generarlo (HdU 19, criterio 5). */
export function ExcelExportDialog({ open, onConfirm, onClose }: ExcelExportDialogProps) {
  const [marcadas, setMarcadas] = useState<ReadonlySet<ExportSection>>(
    () => new Set(EXPORT_SECTIONS),
  );
  const titleId = "excel-export-title";
  const cerrarRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (open) cerrarRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  const alternar = (seccion: ExportSection, marcada: boolean) =>
    setMarcadas((actuales) => {
      const siguientes = new Set(actuales);
      if (marcada) siguientes.add(seccion);
      else siguientes.delete(seccion);
      return siguientes;
    });

  // Siempre en el orden de la lista, como las hojas del Excel.
  const elegidas = EXPORT_SECTIONS.filter((s) => marcadas.has(s));

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
    >
      <div className="w-full max-w-md rounded-xl border border-border-subtle bg-surface-card p-6 shadow-xl">
        <div className="flex items-start justify-between gap-4 border-b border-border-subtle pb-4">
          <div>
            <h2 id={titleId} className="text-base font-bold text-text-strong">
              Exportar a Excel
            </h2>
            <p className="text-xs text-text-subtle">
              Elige las secciones: cada una va en su propia hoja.
            </p>
          </div>
          <button
            ref={cerrarRef}
            type="button"
            onClick={onClose}
            aria-label="Cerrar"
            className="cursor-pointer rounded-lg p-1.5 text-text-subtle hover:bg-warm-100 hover:text-text-strong"
          >
            <Icon name="x" size={18} />
          </button>
        </div>

        <div className="mt-4 flex flex-col gap-3">
          {EXPORT_SECTIONS.map((seccion) => (
            <Switch
              key={seccion}
              checked={marcadas.has(seccion)}
              onChange={(marcada) => alternar(seccion, marcada)}
              label={EXPORT_SECTION_LABELS[seccion].label}
              description={EXPORT_SECTION_LABELS[seccion].description}
            />
          ))}
        </div>

        {elegidas.length === 0 && (
          <p className="mt-3 text-xs font-medium text-danger">
            Elige al menos una sección para generar el Excel.
          </p>
        )}

        <div className="mt-5 flex gap-3">
          <Button type="button" variant="ghost" onClick={onClose} className="flex-1 border border-border-subtle">
            Cancelar
          </Button>
          <Button
            type="button"
            onClick={() => onConfirm(elegidas)}
            disabled={elegidas.length === 0}
            className="flex-1"
          >
            <Icon name="file-spreadsheet" size={15} />
            Generar Excel
          </Button>
        </div>
      </div>
    </div>
  );
}
