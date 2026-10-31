import React from "react";
import { AlertTriangle, FileText } from "lucide-react";

export interface DiscrepancySource {
  document_name: string;
  page_or_sheet: string | null;
  quote: string;
}

export interface DiscrepancyView {
  topic: string;
  description: string;
  conflicting_sources: DiscrepancySource[];
}

export interface DiscrepancyCardProps {
  discrepancy: DiscrepancyView;
  /** Por defecto "Discrepancia detectada: {topic}". */
  title?: string;
  /** Un valor de referencia que no es una cita, p. ej. lo que informa Mercado Público. */
  reference?: { label: string; value: string };
}

export function DiscrepancyCard({
  discrepancy,
  title,
  reference,
}: DiscrepancyCardProps) {
  const { topic, description, conflicting_sources } = discrepancy;
  const cardTitle = title ?? `Discrepancia detectada: ${topic}`;

  return (
    <div
      data-testid="discrepancy-card"
      className="flex flex-col gap-2 rounded-lg border border-warning/40 bg-warning-soft p-3 text-xs text-text-strong shadow-xs"
    >
      <div className="flex items-center gap-1.5 font-semibold text-warning-text">
        <AlertTriangle className="h-4 w-4 shrink-0 text-warning" />
        <span>{cardTitle}</span>
      </div>

      <p className="leading-relaxed text-text-body">{description}</p>

      {reference && (
        <p data-testid="discrepancy-reference" className="text-text-strong font-medium">
          <span className="font-semibold">{reference.label}:</span> {reference.value}
        </p>
      )}

      {conflicting_sources && conflicting_sources.length > 0 && (
        <div className="mt-1 flex flex-col gap-1.5 border-t border-warning/30 pt-2">
          <span className="text-[0.6875rem] font-medium tracking-wide text-warning-text uppercase">
            Fuentes en conflicto:
          </span>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {conflicting_sources.map((src, index) => (
              <div
                key={`${src.document_name}-${index}`}
                className="flex flex-col gap-1 rounded-md border border-border-subtle bg-surface-card/90 p-2 text-text-strong shadow-2xs"
              >
                <div className="flex items-center justify-between gap-1 text-[0.6875rem] font-semibold text-text-body">
                  <div className="flex items-center gap-1 truncate" title={src.document_name}>
                    <FileText className="h-3.5 w-3.5 shrink-0 text-warning" />
                    <span className="truncate">{src.document_name}</span>
                  </div>
                  {src.page_or_sheet && (
                    <span className="shrink-0 rounded-sm bg-warning-soft px-1 py-0.5 text-[0.625rem] font-medium text-warning-text">
                      {src.page_or_sheet}
                    </span>
                  )}
                </div>
                <blockquote className="border-l-2 border-warning pl-1.5 text-[0.6875rem] italic text-text-muted">
                  &quot;{src.quote}&quot;
                </blockquote>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
