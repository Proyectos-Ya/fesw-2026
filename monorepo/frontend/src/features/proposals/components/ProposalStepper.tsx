import { Icon } from "@/features/shared/components/Icon";
import type { ProposalStage, ProposalStatus } from "../types";

const PASOS = [
  { key: "factibilidad", label: "Factibilidad" },
  { key: "redaccion", label: "Redacción" },
  { key: "borrador", label: "Borrador" },
] as const;

const MENSAJE_DE_ETAPA: Record<Exclude<ProposalStage, null>, string> = {
  analyzing: "Analizando bases y experiencia…",
  drafting: "Redactando nombre, descripción y documentos…",
};

function pasoActual(status: ProposalStatus | null, stage: ProposalStage): number {
  if (stage === "drafting") return 1;
  if (status === "READY") return 2;
  return 0;
}

interface ProposalStepperProps {
  status: ProposalStatus | null;
  stage: ProposalStage;
}

/** Dónde va la postulación y, mientras la IA trabaja, en qué etapa está (CA6). */
export function ProposalStepper({ status, stage }: ProposalStepperProps) {
  const actual = pasoActual(status, stage);
  return (
    <div className="mb-6">
      <ol className="flex items-center gap-2" aria-label="Etapas de la postulación">
        {PASOS.map((paso, i) => {
          const hecho = i < actual;
          const enCurso = i === actual;
          return (
            <li
              key={paso.key}
              aria-current={enCurso ? "step" : undefined}
              className="flex flex-1 items-center gap-2"
            >
              <span
                className={`flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                  hecho
                    ? "bg-primary text-on-primary"
                    : enCurso
                      ? "border-2 border-primary text-primary"
                      : "border border-border-default text-text-subtle"
                }`}
              >
                {hecho ? <Icon name="check" size={14} /> : i + 1}
              </span>
              <span
                className={`text-sm font-semibold ${
                  enCurso ? "text-text-strong" : "text-text-muted"
                }`}
              >
                {paso.label}
              </span>
              {i < PASOS.length - 1 && <span className="h-px flex-1 bg-border-subtle" />}
            </li>
          );
        })}
      </ol>
      {stage && (
        <p
          role="status"
          className="mt-4 flex items-center gap-2 rounded-md border border-primary/20 bg-teal-50/60 px-4 py-3 text-sm font-semibold text-teal-700"
        >
          <span className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
          {MENSAJE_DE_ETAPA[stage]}
        </p>
      )}
    </div>
  );
}
