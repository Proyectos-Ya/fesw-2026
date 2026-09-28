"use client";

import { useState } from "react";

import { Button } from "@/features/shared/components/Button";
import { Icon } from "@/features/shared/components/Icon";

import { useTenderExport } from "../hooks/useTenderExport";
import { EXPORT_FORMAT_LABELS, type ExportFormat } from "../types";
import { ExcelExportDialog } from "./ExcelExportDialog";

/** Botones "Exportar a PDF" y "Exportar a Excel" de la ficha (HdU 19). */
export function ExportActions({ tenderId }: { tenderId: string }) {
  const { state, exportAs } = useTenderExport(tenderId);
  const [excelOpen, setExcelOpen] = useState(false);
  const generando = state.status === "generating";

  const etiqueta = (format: ExportFormat) =>
    generando && state.format === format
      ? `Generando ${EXPORT_FORMAT_LABELS[format]}…`
      : `Exportar a ${EXPORT_FORMAT_LABELS[format]}`;

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="ghost"
          onClick={() => void exportAs("pdf", [])}
          disabled={generando}
          isLoading={generando && state.format === "pdf"}
          className="border border-border-subtle px-3 py-2"
        >
          {!(generando && state.format === "pdf") && <Icon name="file-text" size={15} />}
          {etiqueta("pdf")}
        </Button>
        <Button
          type="button"
          variant="ghost"
          onClick={() => setExcelOpen(true)}
          disabled={generando}
          isLoading={generando && state.format === "xlsx"}
          className="border border-border-subtle px-3 py-2"
        >
          {!(generando && state.format === "xlsx") && <Icon name="file-spreadsheet" size={15} />}
          {etiqueta("xlsx")}
        </Button>
      </div>

      {state.status === "queued" && (
        <p role="status" className="flex items-start gap-1.5 text-xs text-text-muted">
          <Icon name="mail" size={14} className="mt-0.5 flex-none" />
          {state.message}
        </p>
      )}
      {state.status === "done" && (
        <p role="status" className="text-xs text-text-muted">
          Tu {EXPORT_FORMAT_LABELS[state.format]} está listo y se descargó.
        </p>
      )}
      {state.status === "error" && (
        <p role="alert" className="text-xs font-medium text-danger">
          {state.message}
        </p>
      )}

      <ExcelExportDialog
        open={excelOpen}
        onClose={() => setExcelOpen(false)}
        onConfirm={(sections) => {
          setExcelOpen(false);
          void exportAs("xlsx", sections);
        }}
      />
    </div>
  );
}
