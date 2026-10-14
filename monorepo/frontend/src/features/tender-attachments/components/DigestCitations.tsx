import { Badge } from "@/features/shared/components/Badge";
import type { DigestCitation } from "../types";

interface DigestCitationsProps {
  citas: DigestCitation[];
}

export function DigestCitations({ citas }: DigestCitationsProps) {
  if (!citas || citas.length === 0) return null;

  const count = citas.length;
  const summaryText = count === 1 ? "Ver cita" : `Ver ${count} citas`;

  return (
    <details className="mt-1 text-xs text-text-muted">
      <summary className="cursor-pointer font-medium text-primary hover:underline select-none">
        {summaryText}
      </summary>
      <div className="mt-2 flex flex-col gap-2 pl-2">
        {citas.map((c, index) => (
          <div
            key={`${c.documento}-${index}`}
            className="rounded-md border border-warm-200 bg-warm-50 p-2"
          >
            <blockquote className="border-l-2 border-primary/40 pl-2 italic text-slate-700">
              &quot;{c.cita}&quot;
            </blockquote>
            <div className="mt-1.5 flex flex-wrap items-center justify-between gap-1 text-[11px] text-text-muted">
              <span>
                {c.documento}
                {c.pagina_u_hoja ? ` · ${c.pagina_u_hoja}` : ""}
              </span>
              {c.verificada ? (
                <Badge tone="success">Cita verificada</Badge>
              ) : (
                <Badge
                  tone="neutral"
                  title="No encontramos este texto en el documento, o el documento no tiene texto (escaneado)."
                >
                  Sin verificar
                </Badge>
              )}
            </div>
          </div>
        ))}
      </div>
    </details>
  );
}
