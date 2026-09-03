import React from "react";
import { AlertTriangle, FileText } from "lucide-react";
import type { DocumentDiscrepancy } from "../types";

interface DiscrepancyCardProps {
  discrepancy: DocumentDiscrepancy;
}

export function DiscrepancyCard({ discrepancy }: DiscrepancyCardProps) {
  const { topic, description, conflicting_sources } = discrepancy;

  return (
    <div
      data-testid="discrepancy-card"
      className="flex flex-col gap-2 rounded-lg border border-amber-300/80 bg-amber-50/90 p-3 text-xs text-amber-950 shadow-xs"
    >
      <div className="flex items-center gap-1.5 font-semibold text-amber-800">
        <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600" />
        <span>Discrepancia detectada: {topic}</span>
      </div>

      <p className="leading-relaxed text-amber-900/90">{description}</p>

      {conflicting_sources && conflicting_sources.length > 0 && (
        <div className="mt-1 flex flex-col gap-1.5 border-t border-amber-200/60 pt-2">
          <span className="text-[11px] font-medium tracking-wide text-amber-800/90 uppercase">
            Fuentes en conflicto:
          </span>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {conflicting_sources.map((src, index) => (
              <div
                key={`${src.document_name}-${index}`}
                className="flex flex-col gap-1 rounded-md border border-amber-200/80 bg-white/80 p-2 text-slate-800 shadow-2xs"
              >
                <div className="flex items-center justify-between gap-1 text-[11px] font-semibold text-slate-700">
                  <div className="flex items-center gap-1 truncate" title={src.document_name}>
                    <FileText className="h-3.5 w-3.5 shrink-0 text-amber-600" />
                    <span className="truncate">{src.document_name}</span>
                  </div>
                  {src.page_or_sheet && (
                    <span className="shrink-0 rounded-sm bg-amber-100/70 px-1 py-0.5 text-[10px] font-medium text-amber-800">
                      {src.page_or_sheet}
                    </span>
                  )}
                </div>
                <blockquote className="border-l-2 border-amber-400 pl-1.5 text-[11px] italic text-slate-600">
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
