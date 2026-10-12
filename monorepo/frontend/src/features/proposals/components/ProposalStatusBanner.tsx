"use client";

import { Button } from "@/features/shared/components/Button";
import { Icon } from "@/features/shared/components/Icon";
import type { ProposalStatusInfo, StatusTone } from "../utils/proposal";

const TONO: Record<StatusTone, { caja: string; titulo: string; icono: string }> = {
  danger: {
    caja: "border-danger/30 bg-danger-soft/40",
    titulo: "text-red-700",
    icono: "octagon-alert",
  },
  warning: {
    caja: "border-warning/30 bg-warning-soft/40",
    titulo: "text-amber-700",
    icono: "triangle-alert",
  },
  info: {
    caja: "border-primary/20 bg-teal-50/60",
    titulo: "text-teal-700",
    icono: "info",
  },
};

interface ProposalStatusBannerProps {
  status: ProposalStatusInfo;
  /** Si el usuario puede ejecutar la acción del banner. */
  canAct: boolean;
  busy: boolean;
  onResume: () => void;
  onReview: () => void;
}

/**
 * Qué pasa con la postulación y qué hacer, arriba del análisis. Reemplaza los
 * avisos sueltos de pausa y de detenida. El texto sale de `proposalStatus`.
 */
export function ProposalStatusBanner({
  status,
  canAct,
  busy,
  onResume,
  onReview,
}: ProposalStatusBannerProps) {
  const tono = TONO[status.tone];
  return (
    <section
      aria-label="Estado de la postulación"
      aria-live="polite"
      className={`mb-6 flex flex-wrap items-start justify-between gap-3 rounded-lg border p-4 text-sm ${tono.caja}`}
    >
      <div className="flex min-w-0 flex-1 items-start gap-3">
        <Icon name={tono.icono} size={18} className={`mt-0.5 shrink-0 ${tono.titulo}`} />
        <div>
          <p className={`font-bold ${tono.titulo}`}>{status.title}</p>
          <p className="mt-0.5 text-text-body">{status.detail}</p>
        </div>
      </div>
      {status.action === "review" && (
        <Button onClick={onReview}>Revisar</Button>
      )}
      {status.action === "resume" && canAct && (
        <Button onClick={onResume} disabled={busy} isLoading={busy}>
          Reanudar
        </Button>
      )}
    </section>
  );
}
