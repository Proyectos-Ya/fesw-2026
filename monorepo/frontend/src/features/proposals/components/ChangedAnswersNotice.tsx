import { Button } from "@/features/shared/components/Button";
import { Icon } from "@/features/shared/components/Icon";
import type { ProposalView } from "../types";

interface ChangedAnswersNoticeProps {
  view: ProposalView;
  canWrite: boolean;
  busy: boolean;
  onSync: () => void;
}

/**
 * Aviso de respuestas del banco que cambiaron desde que la postulación las usó,
 * por ejemplo corregidas en otra pantalla. Aplicarlas vuelve a redactar el
 * borrador o, ante un "No" excluyente, lo deja en pausa.
 */
export function ChangedAnswersNotice({ view, canWrite, busy, onSync }: ChangedAnswersNoticeProps) {
  const cambiadas = view.requirements.filter((r) =>
    view.changed_requirement_ids.includes(r.id),
  );
  if (cambiadas.length === 0) return null;

  const preguntas = new Map(view.questions.map((q) => [q.id, q.question]));
  const respuestas = new Map(view.catalog_items.map((i) => [i.id, i.detail]));

  return (
    <div
      role="status"
      className="mb-6 rounded-lg border border-warning/30 bg-warning-soft/40 p-4 text-sm text-text-body"
    >
      <p className="mb-2 font-semibold text-text-strong">
        Cambiaron respuestas de tu empresa desde que se usaron en esta postulación
      </p>
      <ul className="mb-3 list-disc space-y-1 pl-5">
        {cambiadas.map((r) => {
          const pregunta = r.capability_question_id
            ? preguntas.get(r.capability_question_id)
            : undefined;
          const actual = r.capability_question_id
            ? respuestas.get(`capacidad:${r.capability_question_id}`)
            : undefined;
          return (
            <li key={r.id}>
              {pregunta ?? r.text}{" "}
              <span className="text-text-muted">
                ({actual ? `ahora: ${actual}` : "sin respuesta vigente"})
              </span>
            </li>
          );
        })}
      </ul>
      {canWrite ? (
        <Button onClick={onSync} disabled={busy} isLoading={busy}>
          <Icon name="refresh-cw" size={16} />
          {view.content ? "Actualizar borrador" : "Aplicar las respuestas"}
        </Button>
      ) : (
        <p className="text-text-muted">
          Quien pueda generar postulaciones en esta empresa debe actualizarla.
        </p>
      )}
    </div>
  );
}
