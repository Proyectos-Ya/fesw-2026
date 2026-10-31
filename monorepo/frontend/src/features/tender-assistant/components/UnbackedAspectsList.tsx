import React from "react";
import { HelpCircle } from "lucide-react";

interface UnbackedAspectsListProps {
  aspects?: string[] | null;
}

export function UnbackedAspectsList({ aspects }: UnbackedAspectsListProps) {
  if (!aspects || aspects.length === 0) {
    return null;
  }

  return (
    <div
      data-testid="unbacked-aspects-list"
      className="flex flex-col gap-1.5 rounded-lg border border-border-subtle bg-surface-inset p-2.5 text-xs text-text-body shadow-2xs"
    >
      <div className="flex items-center gap-1.5 font-semibold text-text-body">
        <HelpCircle className="h-3.5 w-3.5 shrink-0 text-text-muted" />
        <span>Aspectos no especificados en los documentos adjuntos:</span>
      </div>

      <ul className="list-disc pl-5 space-y-0.5 text-text-body">
        {aspects.map((aspect, idx) => (
          <li key={idx} className="leading-snug">
            {aspect}
          </li>
        ))}
      </ul>
    </div>
  );
}
