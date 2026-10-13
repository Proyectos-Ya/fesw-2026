import { Icon } from "@/features/shared/components/Icon";
import type { Tender } from "../tenderTypes";
import { callClosingLines } from "../utils/secondCall";

interface CallClosingDatesProps {
  tender: Pick<Tender, "call_number" | "first_call_closing_at" | "second_call_closing_at">;
}

/**
 * Cierre de cada llamado (plan 233, decisión 3). No reemplaza la tarjeta
 * "Cierre", que sigue mostrando el del llamado vigente. Sin fechas por
 * llamado no dibuja nada: una licitación antigua se ve igual que antes.
 */
export function CallClosingDates({ tender }: CallClosingDatesProps) {
  const lines = callClosingLines(tender);
  if (lines.length === 0) return null;
  return (
    <section
      aria-label="Cierre por llamado"
      className="mt-5 rounded-lg border border-border-subtle bg-surface-card p-4 shadow-xs"
    >
      <div className="mb-2 inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-caps text-text-subtle">
        <Icon name="calendar-clock" size={12} color="var(--text-subtle)" />
        Cierre por llamado
      </div>
      <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {lines.map((line) => (
          <div key={line.key}>
            <dt className="text-xs text-text-muted">{line.label}</dt>
            <dd className="font-mono text-sm font-semibold text-text-strong">{line.value}</dd>
            {line.hint && <dd className="mt-0.5 text-xs text-text-subtle">{line.hint}</dd>}
          </div>
        ))}
      </dl>
    </section>
  );
}
