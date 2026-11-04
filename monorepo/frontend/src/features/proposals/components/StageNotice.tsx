"use client";

import { useStageMessage } from "../hooks/useStageMessage";
import type { ProposalStage } from "../types";

/**
 * En qué etapa está la IA mientras trabaja (CA6). Fuera de esos momentos no se
 * muestra nada: la página no es un asistente por pasos y no debe parecer que
 * queda algo pendiente. Va dentro de los avisos flotantes de `ProposalView`,
 * para que se vea desde cualquier parte de la página.
 */
export function StageNotice({ stage }: { stage: ProposalStage }) {
  const mensaje = useStageMessage(stage);
  if (!mensaje) return null;
  return (
    <p
      role="status"
      className="pointer-events-auto flex w-full max-w-xl items-center gap-2 rounded-md border border-primary/20 bg-primary-soft px-4 py-3 text-sm font-semibold text-text-link shadow-lg"
    >
      <span className="size-4 shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent" />
      {mensaje}
    </p>
  );
}
