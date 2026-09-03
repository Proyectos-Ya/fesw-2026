import React from "react";
import { MessageSquareQuote } from "lucide-react";

interface InsufficientInfoBannerProps {
  hasSufficientInfo?: boolean | null;
}

export function InsufficientInfoBanner({
  hasSufficientInfo,
}: InsufficientInfoBannerProps) {
  if (hasSufficientInfo !== false) {
    return null;
  }

  return (
    <div
      data-testid="insufficient-info-banner"
      className="flex items-start gap-2 rounded-lg border border-blue-200 bg-blue-50/80 p-2.5 text-xs text-blue-900 shadow-2xs"
    >
      <MessageSquareQuote className="h-4 w-4 shrink-0 text-blue-600 mt-0.5" />
      <div className="flex flex-col gap-0.5">
        <span className="font-semibold text-blue-900">
          Información no especificada en las bases
        </span>
        <p className="leading-relaxed text-blue-800">
          Se sugiere realizar la consulta formal mediante el Foro de Preguntas de Mercado Público antes de la fecha de cierre de la licitación.
        </p>
      </div>
    </div>
  );
}
