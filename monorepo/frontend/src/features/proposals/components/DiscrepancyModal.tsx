"use client";

import { Button } from "@/features/shared/components/Button";
import { Dialog } from "@/features/shared/components/Dialog";
import { formatDateTime } from "@/features/matches/utils/format";
import { pauseOrigin, pausedRequirement, questionFor } from "../utils/proposal";
import type { DecisionAction, ProposalView } from "../types";

interface DiscrepancyModalProps {
  view: ProposalView;
  open: boolean;
  busy: boolean;
  canWrite: boolean;
  onClose: () => void;
  onUpdateAnswer: (questionId: string, label: string) => void;
  onDecide: (requirementId: string, action: DecisionAction) => void;
}

/**
 * Aviso ante un "No" a una exigencia excluyente (CA7). Ofrece actualizar la
 * respuesta, continuar con advertencia (CA8) o detener (CA9). Si el "No" viene
 * de una respuesta anterior de la empresa, lo dice, para que no sorprenda.
 */
export function DiscrepancyModal({
  view,
  open,
  busy,
  canWrite,
  onClose,
  onUpdateAnswer,
  onDecide,
}: DiscrepancyModalProps) {
  const requisito = pausedRequirement(view);
  if (!requisito) return null;
  const pregunta = questionFor(view, requisito);
  const origen = pauseOrigin(view);
  const afirmativas = pregunta?.options.filter((o) => o.polarity !== "negativa") ?? [];

  return (
    <Dialog open={open} title="Posible incumplimiento de las bases" onClose={onClose}>
      <div className="flex flex-col gap-3 text-sm text-text-body">
        <p>
          Las bases exigen: <strong>{requisito.text}</strong>
        </p>
        {origen && (
          <p className="rounded-md bg-warm-100 px-3 py-2 text-xs text-text-muted">
            La empresa respondió &quot;No&quot; el {formatDateTime(origen.answeredAt)}
            {origen.fromAnotherTender ? " en otra licitación" : ""}. Si ya no es así,
            actualiza la respuesta.
          </p>
        )}
        <p className="font-semibold text-red-600">
          Recomendamos no postular: la empresa declaró no cumplir esta exigencia
          excluyente.
        </p>

        {canWrite ? (
          <div className="mt-2 flex flex-col gap-2">
            {pregunta && afirmativas.length > 0 && (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-semibold text-text-muted">
                  Actualizar respuesta:
                </span>
                {afirmativas.map((opcion) => (
                  <Button
                    key={opcion.label}
                    variant="ghost"
                    className="border border-border-strong bg-white"
                    disabled={busy}
                    onClick={() => onUpdateAnswer(pregunta.id, opcion.label)}
                  >
                    {opcion.label}
                  </Button>
                ))}
              </div>
            )}
            <div className="flex flex-wrap gap-2">
              <Button
                disabled={busy}
                onClick={() => onDecide(requisito.id, "continue")}
              >
                Continuar con advertencia
              </Button>
              <Button
                variant="ghost"
                className="border border-border-strong"
                disabled={busy}
                onClick={() => onDecide(requisito.id, "stop")}
              >
                Detener postulación
              </Button>
            </div>
          </div>
        ) : (
          <p className="text-xs text-text-muted">
            Solo quienes pueden generar postulaciones en esta empresa pueden decidir.
          </p>
        )}
      </div>
    </Dialog>
  );
}
