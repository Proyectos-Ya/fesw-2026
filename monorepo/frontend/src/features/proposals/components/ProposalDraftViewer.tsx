"use client";

import { useState } from "react";
import { Button } from "@/features/shared/components/Button";
import { Icon } from "@/features/shared/components/Icon";
import { HighlightedText } from "./HighlightedText";
import { RegenerateDialog } from "./RegenerateDialog";
import type { DraftParagraph, DraftSection, ProposalView } from "../types";

interface ProposalDraftViewerProps {
  view: ProposalView;
  canWrite: boolean;
  busy: boolean;
  onRegenerate: (instructions: string) => void;
  onDownload: () => void;
}

function textoDe(seccion: DraftSection): string {
  return seccion.paragraphs.map((p) => p.text).join("\n\n");
}

function BotonCopiar({ texto, etiqueta }: { texto: string; etiqueta: string }) {
  const [copiado, setCopiado] = useState(false);
  return (
    <Button
      variant="ghost"
      className="px-2 py-1 text-xs"
      aria-label={`Copiar ${etiqueta}`}
      onClick={async () => {
        await navigator.clipboard.writeText(texto);
        setCopiado(true);
        setTimeout(() => setCopiado(false), 2000);
      }}
    >
      <Icon name={copiado ? "check" : "copy"} size={14} />
      {copiado ? "Copiado" : "Copiar"}
    </Button>
  );
}

interface ParrafoProps {
  parrafo: DraftParagraph;
  seleccionado: boolean;
  onSelect: () => void;
}

function Parrafo({ parrafo, seleccionado, onSelect }: ParrafoProps) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={seleccionado}
      className={`w-full rounded-md px-3 py-2 text-left text-sm leading-relaxed text-text-body transition-colors ${
        seleccionado ? "bg-teal-50 ring-1 ring-primary/30" : "hover:bg-warm-100/60"
      }`}
    >
      <HighlightedText text={parrafo.text} />
    </button>
  );
}

function SourcePanel({ parrafo }: { parrafo: DraftParagraph | null }) {
  return (
    <aside
      aria-label="Fuentes del párrafo"
      className="rounded-lg border border-border-subtle bg-surface-card p-4 lg:sticky lg:top-6"
    >
      <h3 className="mb-2 text-sm font-bold text-text-strong">Fuentes</h3>
      {parrafo === null ? (
        <p className="text-xs text-text-muted">
          Selecciona un párrafo para ver en qué parte del perfil de tu empresa se basa.
        </p>
      ) : parrafo.sources.length === 0 ? (
        <p className="text-xs text-text-muted">
          Este párrafo no cita datos de la empresa: sale de las bases de la licitación.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {parrafo.sources.map((fuente) => (
            <li
              key={fuente.id}
              className="rounded-md bg-warm-100/60 px-3 py-2 text-xs text-text-body"
            >
              {fuente.label}
            </li>
          ))}
        </ul>
      )}
      {parrafo !== null && parrafo.placeholders.length > 0 && (
        <p className="mt-3 text-xs font-semibold text-amber-700">
          Falta completar: {parrafo.placeholders.join(", ")}.
        </p>
      )}
    </aside>
  );
}

/**
 * El borrador redactado (CA1). Nombre, descripción y documentos se copian desde
 * acá al formulario de la Compra Ágil; el documento técnico, si las bases lo
 * exigen, se descarga en Word (CA3). Cada párrafo muestra sus fuentes (CA5) y
 * los vacíos van resaltados (CA2).
 */
export function ProposalDraftViewer({
  view,
  canWrite,
  busy,
  onRegenerate,
  onDownload,
}: ProposalDraftViewerProps) {
  const [seleccionado, setSeleccionado] = useState<string | null>(null);
  const [regenerando, setRegenerando] = useState(false);
  const contenido = view.content;
  if (!contenido) return null;

  const secciones: { key: string; titulo: string; seccion: DraftSection }[] = [
    { key: "nombre", titulo: "Nombre de la oferta", seccion: contenido.offer_name },
    { key: "descripcion", titulo: "Descripción de la oferta", seccion: contenido.offer_description },
  ];
  const todos: Record<string, DraftParagraph> = {};
  secciones.forEach(({ key, seccion }) =>
    seccion.paragraphs.forEach((p, i) => (todos[`${key}-${i}`] = p)),
  );
  contenido.technical_document?.sections.forEach((s) =>
    s.paragraphs.forEach((p, i) => (todos[`tecnico-${s.key}-${i}`] = p)),
  );
  const parrafoSeleccionado = seleccionado ? (todos[seleccionado] ?? null) : null;

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-text-muted">
          Copia cada sección al formulario de la Compra Ágil. Revisa lo resaltado antes de
          enviar.
        </p>
        {canWrite && !view.is_expired && (
          <Button
            variant="ghost"
            className="border border-border-strong"
            disabled={busy}
            onClick={() => setRegenerando(true)}
          >
            <Icon name="refresh-cw" size={16} />
            Regenerar
          </Button>
        )}
      </div>

      {view.warnings.length > 0 && (
        <div
          role="alert"
          className="mb-5 rounded-lg border border-warning/30 bg-warning-soft/40 p-4 text-sm"
        >
          <p className="mb-1 font-bold text-amber-700">Revisar antes de enviar</p>
          <ul className="list-disc pl-5 text-text-body">
            {view.warnings.map((w) => (
              <li key={w.requirement_id}>{w.text}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_16rem]">
        <div className="flex flex-col gap-5">
          {secciones.map(({ key, titulo, seccion }) => (
            <section
              key={key}
              aria-label={titulo}
              className="rounded-lg border border-border-subtle bg-white p-4"
            >
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-sm font-bold text-text-strong">{titulo}</h3>
                <BotonCopiar texto={textoDe(seccion)} etiqueta={titulo.toLowerCase()} />
              </div>
              {seccion.paragraphs.map((p, i) => (
                <Parrafo
                  key={i}
                  parrafo={p}
                  seleccionado={seleccionado === `${key}-${i}`}
                  onSelect={() => setSeleccionado(`${key}-${i}`)}
                />
              ))}
            </section>
          ))}

          <section
            aria-label="Documentos necesarios"
            className="rounded-lg border border-border-subtle bg-white p-4"
          >
            <h3 className="mb-2 text-sm font-bold text-text-strong">Documentos necesarios</h3>
            {contenido.required_documents.paragraphs.length === 0 ? (
              <p className="text-sm text-text-muted">Las bases no piden adjuntar documentos.</p>
            ) : (
              <ul className="list-disc pl-5 text-sm text-text-body">
                {contenido.required_documents.paragraphs.map((p, i) => (
                  <li key={i}>
                    <HighlightedText text={p.text} />
                  </li>
                ))}
              </ul>
            )}
          </section>

          {contenido.technical_document && (
            <section
              aria-label="Documento técnico"
              className="rounded-lg border border-primary/20 bg-teal-50/30 p-4"
            >
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-sm font-bold text-text-strong">Documento técnico</h3>
                <Button onClick={onDownload} className="px-3 py-1.5 text-xs">
                  <Icon name="download" size={14} />
                  Exportar a .docx
                </Button>
              </div>
              {contenido.technical_document.sections.map((s) => (
                <div key={s.key} className="mb-3">
                  <h4 className="px-3 text-xs font-bold uppercase tracking-wide text-text-muted">
                    {s.title}
                  </h4>
                  {s.paragraphs.map((p, i) => (
                    <Parrafo
                      key={i}
                      parrafo={p}
                      seleccionado={seleccionado === `tecnico-${s.key}-${i}`}
                      onSelect={() => setSeleccionado(`tecnico-${s.key}-${i}`)}
                    />
                  ))}
                </div>
              ))}
            </section>
          )}
        </div>

        <SourcePanel parrafo={parrafoSeleccionado} />
      </div>

      <RegenerateDialog
        open={regenerando}
        busy={busy}
        onClose={() => setRegenerando(false)}
        onSubmit={(instrucciones) => {
          setRegenerando(false);
          onRegenerate(instrucciones);
        }}
      />
    </div>
  );
}
