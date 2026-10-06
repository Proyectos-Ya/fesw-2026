import type { ProposalStage } from "../types";

const MENSAJE_DE_ETAPA: Record<Exclude<ProposalStage, null>, string> = {
  analyzing: "Analizando bases y experiencia…",
  drafting: "Redactando nombre, descripción y documentos…",
};

/**
 * En qué etapa está la IA mientras trabaja (CA6). Fuera de esos momentos no se
 * muestra nada: la página no es un asistente por pasos y no debe parecer que
 * queda algo pendiente.
 */
export function StageNotice({ stage }: { stage: ProposalStage }) {
  if (!stage) return null;
  return (
    <p
      role="status"
      className="mb-6 flex items-center gap-2 rounded-md border border-primary/20 bg-teal-50/60 px-4 py-3 text-sm font-semibold text-teal-700"
    >
      <span className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
      {MENSAJE_DE_ETAPA[stage]}
    </p>
  );
}
