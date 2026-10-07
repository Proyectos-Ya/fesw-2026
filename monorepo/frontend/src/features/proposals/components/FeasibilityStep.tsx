"use client";

import { useState } from "react";
import { formatDateTime } from "@/features/matches/utils/format";
import { Badge, type BadgeTone } from "@/features/shared/components/Badge";
import { Button } from "@/features/shared/components/Button";
import { Icon } from "@/features/shared/components/Icon";
import { EvidenceForm } from "./EvidenceForm";
import {
  canGenerate,
  currentAnswer,
  esDeclaracionDeHabilidad,
  questionFor,
  requirementsToReanswer,
} from "../utils/proposal";
import {
  KINDS_SIN_PREGUNTA,
  type CapabilityEvidenceInput,
  type CapabilityQuestion,
  type PendingAnswer,
  type ProposalView,
  type Requirement,
} from "../types";

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
  /** La opción que se está guardando, para mostrar que carga en ese botón. */
  answering?: PendingAnswer | null;
  onAnswer: (questionId: string, label: string) => void;
  onGenerate: () => void;
  /** Guarda un proyecto de experiencia. Sin esta prop no se ofrece agregarlos. */
  onAddEvidence?: (questionId: string, data: CapabilityEvidenceInput) => Promise<void>;
  /** La pregunta de proyectos a la que se acaba de responder "Sí". */
  suggestedEvidence?: string | null;
  onDismissEvidence?: () => void;
}

interface PreguntaProps {
  view: ProposalView;
  requisito: Requirement;
  editable: boolean;
  busy: boolean;
  answering: PendingAnswer | null;
  onAnswer: (questionId: string, label: string) => void;
  className: string;
}

function Pregunta({
  view,
  requisito: r,
  editable,
  busy,
  answering,
  onAnswer,
  className,
}: PreguntaProps) {
  const pregunta = questionFor(view, r);
  return (
    <li className={`rounded-md border p-4 ${className}`}>
      <p className="text-sm font-semibold text-text-strong">{pregunta?.question ?? r.text}</p>
      <p className="mt-1 text-xs text-text-muted">
        {r.suggested
          ? "Sugerida para fortalecer tu oferta: la respuesta se usa al redactar la descripción."
          : `Las bases dicen: ${r.text}${r.mandatory ? " (excluyente)" : " (deseable)"}`}
      </p>
      {pregunta && (
        <div className="mt-3 flex flex-wrap gap-2">
          {pregunta.options.map((opcion) => (
            <Button
              key={opcion.label}
              variant="ghost"
              className="border border-border-strong bg-white"
              disabled={!editable || busy}
              isLoading={
                answering?.questionId === pregunta.id && answering.label === opcion.label
              }
              onClick={() => onAnswer(pregunta.id, opcion.label)}
            >
              {opcion.label}
            </Button>
          ))}
        </div>
      )}
    </li>
  );
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
            <span className="text-text-body">{r.text}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

interface EvaluadaProps {
  view: ProposalView;
  requisito: Requirement;
  /** Se puede cambiar la respuesta: con permiso, vigente y en FEASIBILITY o READY. */
  puedeCambiar: boolean;
  /** Se puede agregar un proyecto: con permiso, vigente y con `onAddEvidence`. */
  puedeAgregar: boolean;
  abierta: boolean;
  busy: boolean;
  answering: PendingAnswer | null;
  onToggle: () => void;
  onAnswer: (questionId: string, label: string) => void;
  onAddProject: (pregunta: CapabilityQuestion) => void;
}

/**
 * Una exigencia ya evaluada. Si viene de una pregunta del banco, la respuesta
 * se puede cambiar ahí mismo; si es un "Sí" de proyectos, se puede respaldar
 * con un proyecto.
 */
function Evaluada({
  view,
  requisito: r,
  puedeCambiar,
  puedeAgregar,
  abierta,
  busy,
  answering,
  onToggle,
  onAnswer,
  onAddProject,
}: EvaluadaProps) {
  const pregunta = questionFor(view, r);
  const actual = pregunta ? currentAnswer(view, pregunta.id) : null;
  const deOtraLicitacion =
    actual !== null && actual.tender_id !== null && actual.tender_id !== view.tender_id;
  const conProyecto =
    puedeAgregar &&
    pregunta?.kind === "experiencia_proyecto" &&
    actual?.polarity === "afirmativa";

  return (
    <li className="rounded-md border border-border-subtle bg-white px-3 py-2 text-sm">
      <div className="flex items-start justify-between gap-3">
        <span className="text-text-body">
          {r.text}
          {r.mandatory && (
            <span className="ml-2 text-xs font-semibold text-text-subtle">Excluyente</span>
          )}
        </span>
        <Badge tone={ESTADO[r.status].tone}>{ESTADO[r.status].label}</Badge>
      </div>
      {((pregunta && puedeCambiar) || conProyecto) && (
        <div className="mt-2 flex flex-wrap gap-2">
          {pregunta && puedeCambiar && (
            <Button
              variant="ghost"
              className="px-2 py-1 text-xs"
              aria-expanded={abierta}
              onClick={onToggle}
            >
              <Icon name="pencil" size={14} />
              Cambiar respuesta
            </Button>
          )}
          {conProyecto && pregunta && (
            <Button
              variant="ghost"
              className="px-2 py-1 text-xs"
              disabled={busy}
              onClick={() => onAddProject(pregunta)}
            >
              <Icon name="plus" size={14} />
              Agregar proyecto
            </Button>
          )}
        </div>
      )}
      {pregunta && puedeCambiar && abierta && (
        <div className="mt-2 rounded-md bg-warm-100/50 p-3">
          <p className="text-xs font-semibold text-text-strong">{pregunta.question}</p>
          {deOtraLicitacion && (
            <p className="mt-1 text-xs text-text-muted">
              {actual?.answered_at
                ? `Respondida el ${formatDateTime(actual.answered_at)} en otra licitación.`
                : "Respondida en otra licitación."}{" "}
              Cambiarla la actualiza para todas tus postulaciones.
            </p>
          )}
          <div className="mt-2 flex flex-wrap gap-2">
            {pregunta.options.map((opcion) => {
              const elegida = actual?.detail === opcion.label;
              return (
                <Button
                  key={opcion.label}
                  variant="ghost"
                  aria-pressed={elegida}
                  className={`border bg-white ${
                    elegida ? "border-primary text-primary ring-1 ring-primary/30" : "border-border-strong"
                  }`}
                  disabled={busy}
                  isLoading={
                    answering?.questionId === pregunta.id && answering.label === opcion.label
                  }
                  onClick={() => onAnswer(pregunta.id, opcion.label)}
                >
                  {opcion.label}
                </Button>
              );
            })}
          </div>
        </div>
      )}
    </li>
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
  answering = null,
  onAnswer,
  onGenerate,
  onAddEvidence,
  suggestedEvidence = null,
  onDismissEvidence,
}: FeasibilityStepProps) {
  // Qué exigencia tiene abiertas sus opciones, y en qué versión del borrador.
  // Al guardar una respuesta el borrador cambia de versión y el panel se
  // cierra solo; si falla, sigue abierto para reintentar.
  const [cambiando, setCambiando] = useState<{ id: string; version: string } | null>(null);
  const [proyectoPara, setProyectoPara] = useState<CapabilityQuestion | null>(null);

  const sinPregunta = (r: Requirement) => KINDS_SIN_PREGUNTA.indexOf(r.kind) !== -1;
  const pendientes = view.requirements.filter(
    (r) => !sinPregunta(r) && r.status === "desconocido",
  );
  const deNuevo = requirementsToReanswer(view);
  const evaluadas = view.requirements.filter(
    (r) => !sinPregunta(r) && r.status !== "desconocido" && !deNuevo.includes(r),
  );
  const condiciones = view.requirements.filter((r) => r.kind === "condicion");
  const documentos = view.requirements.filter(
    (r) => r.kind === "documento" && !esDeclaracionDeHabilidad(r.text),
  );
  const listo = canGenerate(view);
  const editable = canWrite && !view.is_expired && view.status === "FEASIBILITY";
  // Sin esto, en pausa los botones quedan deshabilitados sin explicación.
  const motivoBloqueo =
    view.is_expired
      ? null
      : view.status === "PAUSED"
        ? "Podrás responder estas preguntas cuando resuelvas la exigencia excluyente en pausa."
        : view.status === "STOPPED"
          ? "La postulación está detenida. Reanúdala para responder estas preguntas."
          : null;
  const preguntaProps = { view, editable, busy, answering, onAnswer };
  // En pausa la respuesta se corrige desde el aviso; detenida, hay que reanudar.
  const puedeCambiar =
    canWrite && !view.is_expired && (view.status === "FEASIBILITY" || view.status === "READY");
  const puedeAgregar = canWrite && !view.is_expired && onAddEvidence !== undefined;
  const sugerida = puedeAgregar
    ? (view.questions.find(
        (q) => q.id === suggestedEvidence && q.kind === "experiencia_proyecto",
      ) ?? null)
    : null;

  return (
    <div>
      {sugerida && (
        <section
          role="status"
          aria-label="Agregar un proyecto"
          className="mb-5 flex flex-wrap items-start justify-between gap-3 rounded-md border border-primary/20 bg-teal-50/60 p-4 text-sm text-teal-700"
        >
          <p className="flex items-start gap-2">
            <Icon name="info" size={16} className="mt-0.5 shrink-0" />
            <span>
              Respondiste &quot;Sí&quot; a &quot;{sugerida.question}&quot;. Si agregas un
              proyecto que lo respalde, la redacción lo podrá citar.
            </span>
          </p>
          <div className="flex gap-2">
            <Button
              variant="ghost"
              className="px-3 py-1.5 text-xs"
              onClick={() => onDismissEvidence?.()}
            >
              Ahora no
            </Button>
            <Button className="px-3 py-1.5 text-xs" onClick={() => setProyectoPara(sugerida)}>
              Agregar proyecto
            </Button>
          </div>
        </section>
      )}

      {deNuevo.length > 0 && (
        <section className="mb-5" aria-labelledby="responder-de-nuevo">
          <h3 id="responder-de-nuevo" className="mb-1 text-sm font-bold text-text-strong">
            Responder de nuevo ({deNuevo.length})
          </h3>
          <p className="mb-2 text-xs text-text-muted">
            La empresa declaró no cumplir esta exigencia excluyente y la postulación se
            detuvo. Si eso cambió, responde de nuevo. Si vuelves a responder &quot;No&quot;,
            la postulación vuelve a quedar en pausa.
          </p>
          <ul className="flex flex-col gap-3">
            {deNuevo.map((r) => (
              <Pregunta
                key={r.id}
                requisito={r}
                className="border-warning/30 bg-warning-soft/30"
                {...preguntaProps}
              />
            ))}
          </ul>
        </section>
      )}

      {pendientes.length > 0 && (
        <section className="mb-5" aria-labelledby="preguntas-pendientes">
          <h3 id="preguntas-pendientes" className="mb-2 text-sm font-bold text-text-strong">
            Preguntas por responder ({pendientes.length})
          </h3>
          {motivoBloqueo && (
            <p className="mb-2 flex items-start gap-2 text-xs font-semibold text-amber-700">
              <Icon name="lock" size={14} className="mt-px shrink-0" />
              {motivoBloqueo}
            </p>
          )}
          <ul className="flex flex-col gap-3">
            {pendientes.map((r) => (
              <Pregunta
                key={r.id}
                requisito={r}
                className="border-primary/20 bg-teal-50/40"
                {...preguntaProps}
              />
            ))}
          </ul>
        </section>
      )}

      {evaluadas.length > 0 && (
        <section className="mb-5" aria-labelledby="exigencias-evaluadas">
          <h3 id="exigencias-evaluadas" className="mb-2 text-sm font-bold text-text-strong">
            Exigencias evaluadas
          </h3>
          <ul className="flex flex-col gap-2">
            {evaluadas.map((r) => (
              <Evaluada
                key={r.id}
                view={view}
                requisito={r}
                puedeCambiar={puedeCambiar}
                puedeAgregar={puedeAgregar}
                abierta={cambiando?.id === r.id && cambiando.version === view.updated_at}
                busy={busy}
                answering={answering}
                onToggle={() =>
                  setCambiando((actual) =>
                    actual?.id === r.id && actual.version === view.updated_at
                      ? null
                      : { id: r.id, version: view.updated_at },
                  )
                }
                onAnswer={onAnswer}
                onAddProject={setProyectoPara}
              />
            ))}
          </ul>
        </section>
      )}
      <Lista titulo="Condiciones del servicio" items={condiciones} />
      <Lista titulo="Documentos a adjuntar" items={documentos} />

      {view.technical_document_reason && (
        <p className="mb-5 flex items-start gap-2 rounded-md border border-border-subtle bg-warm-100/50 px-3 py-2 text-sm text-text-body">
          <Icon name="file-text" size={16} className="mt-0.5 shrink-0" />
          <span>
            <strong>
              {view.requires_technical_document
                ? "Las bases piden un documento técnico. "
                : view.technical_document_ambiguous
                  ? "Las bases mencionan un documento técnico, pero no indican si va con la cotización. "
                  : "Documento técnico: opcional. "}
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
              {deNuevo.length > 0 && pendientes.length === 0
                ? "Responde de nuevo la exigencia excluyente para poder redactar."
                : "Responde las preguntas pendientes para poder redactar."}
            </p>
          )}
        </div>
      )}

      {onAddEvidence && (
        <EvidenceForm
          open={proyectoPara !== null}
          question={proyectoPara}
          onClose={() => setProyectoPara(null)}
          onSubmit={onAddEvidence}
        />
      )}
    </div>
  );
}
