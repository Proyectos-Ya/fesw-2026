"use client";

import { Badge, type BadgeTone } from "@/features/shared/components/Badge";
import { Button } from "@/features/shared/components/Button";
import { Icon } from "@/features/shared/components/Icon";
import { canGenerate, questionFor } from "../utils/proposal";
import { KINDS_SIN_PREGUNTA, type ProposalView, type Requirement } from "../types";

const ESTADO: Record<Requirement["status"], { label: string; tone: BadgeTone }> = {
  cumple: { label: "Cumple", tone: "success" },
  no_cumple: { label: "No cumple", tone: "danger" },
  parcial: { label: "Parcial", tone: "warning" },
  desconocido: { label: "Por responder", tone: "info" },
};

interface FeasibilityStepProps {
  view: ProposalView;
  canWrite: boolean;
  busy: boolean;
  onAnswer: (questionId: string, label: string) => void;
  onGenerate: () => void;
}

function Lista({ titulo, items }: { titulo: string; items: Requirement[] }) {
  if (items.length === 0) return null;
  return (
    <section className="mb-5">
      <h3 className="mb-2 text-sm font-bold text-text-strong">{titulo}</h3>
      <ul className="flex flex-col gap-2">
        {items.map((r) => (
          <li
            key={r.id}
            className="flex items-start justify-between gap-3 rounded-md border border-border-subtle bg-white px-3 py-2 text-sm"
          >
            <span className="text-text-body">
              {r.text}
              {r.mandatory && KINDS_SIN_PREGUNTA.indexOf(r.kind) === -1 && (
                <span className="ml-2 text-xs font-semibold text-text-subtle">
                  Excluyente
                </span>
              )}
            </span>
            {KINDS_SIN_PREGUNTA.indexOf(r.kind) === -1 && (
              <Badge tone={ESTADO[r.status].tone}>{ESTADO[r.status].label}</Badge>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

/**
 * Fase 1: las exigencias de las bases frente a lo que se sabe de la empresa, y
 * las preguntas que faltan. Las condiciones del servicio y los documentos se
 * muestran pero no se preguntan: definen la oferta, no a la empresa.
 */
export function FeasibilityStep({
  view,
  canWrite,
  busy,
  onAnswer,
  onGenerate,
}: FeasibilityStepProps) {
  const sinPregunta = (r: Requirement) => KINDS_SIN_PREGUNTA.indexOf(r.kind) !== -1;
  const pendientes = view.requirements.filter(
    (r) => !sinPregunta(r) && r.status === "desconocido",
  );
  const evaluadas = view.requirements.filter(
    (r) => !sinPregunta(r) && r.status !== "desconocido",
  );
  const condiciones = view.requirements.filter((r) => r.kind === "condicion");
  const documentos = view.requirements.filter((r) => r.kind === "documento");
  const listo = canGenerate(view);
  const editable = canWrite && !view.is_expired && view.status === "FEASIBILITY";

  return (
    <div>
      {pendientes.length > 0 && (
        <section className="mb-5" aria-labelledby="preguntas-pendientes">
          <h3 id="preguntas-pendientes" className="mb-2 text-sm font-bold text-text-strong">
            Preguntas por responder ({pendientes.length})
          </h3>
          <ul className="flex flex-col gap-3">
            {pendientes.map((r) => {
              const pregunta = questionFor(view, r);
              return (
                <li
                  key={r.id}
                  className="rounded-md border border-primary/20 bg-teal-50/40 p-4"
                >
                  <p className="text-sm font-semibold text-text-strong">
                    {pregunta?.question ?? r.text}
                  </p>
                  <p className="mt-1 text-xs text-text-muted">
                    Las bases dicen: {r.text}
                    {r.mandatory ? " (excluyente)" : " (deseable)"}
                  </p>
                  {pregunta && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {pregunta.options.map((opcion) => (
                        <Button
                          key={opcion.label}
                          variant="ghost"
                          className="border border-border-strong bg-white"
                          disabled={!editable || busy}
                          onClick={() => onAnswer(pregunta.id, opcion.label)}
                        >
                          {opcion.label}
                        </Button>
                      ))}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      )}

      <Lista titulo="Exigencias evaluadas" items={evaluadas} />
      <Lista titulo="Condiciones del servicio" items={condiciones} />
      <Lista titulo="Documentos a adjuntar" items={documentos} />

      {view.technical_document_reason && (
        <p className="mb-5 flex items-start gap-2 rounded-md border border-border-subtle bg-warm-100/50 px-3 py-2 text-sm text-text-body">
          <Icon name="file-text" size={16} className="mt-0.5 shrink-0" />
          <span>
            <strong>
              {view.requires_technical_document
                ? "Las bases exigen documento técnico. "
                : "No se exige documento técnico. "}
            </strong>
            {view.technical_document_reason}
          </span>
        </p>
      )}

      {canWrite && view.status === "FEASIBILITY" && !view.is_expired && (
        <div className="flex flex-col items-start gap-2">
          <Button onClick={onGenerate} disabled={!listo || busy} isLoading={busy && listo}>
            <Icon name="sparkles" size={16} />
            Redactar borrador
          </Button>
          {!listo && (
            <p className="text-xs text-text-muted">
              Responde las preguntas pendientes para poder redactar.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
