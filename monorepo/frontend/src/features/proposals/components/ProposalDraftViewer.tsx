"use client";

import { useId, useState } from "react";
import { Button } from "@/features/shared/components/Button";
import { Icon } from "@/features/shared/components/Icon";
import { HighlightedText } from "./HighlightedText";
import { NextSteps } from "./NextSteps";
import { RegenerateDialog } from "./RegenerateDialog";
import { MAX_DETALLE_COTIZACION } from "../utils/proposal";
import type { DraftParagraph, DraftSection, ProposalStage, ProposalView } from "../types";

interface ProposalDraftViewerProps {
  view: ProposalView;
  tenderCode?: string | null;
  canWrite: boolean;
  busy: boolean;
  /** Etapa de la IA en curso: al redactar o regenerar, el borrador se cubre. */
  stage?: ProposalStage;
  onRegenerate: (instructions: string) => void;
  onDownload: () => void;
  onRequestTechnical: () => void;
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

/**
 * Cuántos caracteres se copian al "Detalle de la cotización", que en Mercado
 * Público acepta 255. Cuenta el mismo texto que copia el botón.
 */
function ContadorDetalle({ texto }: { texto: string }) {
  const largo = texto.length;
  const excede = largo > MAX_DETALLE_COTIZACION;
  return (
    <div className="mt-2 flex flex-col items-end gap-1 px-3">
      <p className={`text-xs ${excede ? "font-semibold text-danger" : "text-text-muted"}`}>
        {largo}/{MAX_DETALLE_COTIZACION}
      </p>
      {excede && (
        <p className="self-start text-xs text-danger">
          Supera los {MAX_DETALLE_COTIZACION} caracteres que acepta Mercado Público. Acórtalo
          antes de pegarlo, o regenera pidiendo un texto más corto.
        </p>
      )}
    </div>
  );
}

function ContenidoFuentes({ parrafo }: { parrafo: DraftParagraph }) {
  return (
    <>
      {parrafo.sources.length === 0 ? (
        <p>Este párrafo no cita datos de la empresa: sale de las bases de la licitación.</p>
      ) : (
        <>
          <p className="mb-1.5 font-semibold text-text-strong">Se basa en:</p>
          <ul className="flex flex-col gap-1.5">
            {parrafo.sources.map((fuente) => (
              <li key={fuente.id} className="rounded-md bg-warm-100/60 px-2 py-1.5">
                {fuente.label}
              </li>
            ))}
          </ul>
        </>
      )}
      {parrafo.placeholders.length > 0 && (
        <p className="mt-2 font-semibold text-amber-700">
          Falta completar: {parrafo.placeholders.join(", ")}.
        </p>
      )}
    </>
  );
}

/**
 * Las fuentes de un párrafo (CA5), en un globo junto a él. Se abre al pasar el
 * cursor, con el foco del teclado o al tocar en el celular, y se cierra con
 * Escape o al salir. Reemplaza al panel lateral, que quedaba arriba de la
 * página mientras se revisaba el borrador más abajo.
 */
function FuentesDelParrafo({ parrafo }: { parrafo: DraftParagraph }) {
  const [abierto, setAbierto] = useState(false);
  const idGlobo = useId();
  const resumen = parrafo.text.length > 60 ? `${parrafo.text.slice(0, 60)}…` : parrafo.text;
  return (
    <span
      className="relative shrink-0"
      onMouseEnter={() => setAbierto(true)}
      onMouseLeave={() => setAbierto(false)}
    >
      <button
        type="button"
        aria-label={`Fuentes del párrafo: ${resumen}`}
        aria-expanded={abierto}
        aria-describedby={abierto ? idGlobo : undefined}
        onClick={() => setAbierto(true)}
        onFocus={() => setAbierto(true)}
        onBlur={() => setAbierto(false)}
        onKeyDown={(evento) => {
          if (evento.key === "Escape") setAbierto(false);
        }}
        className="inline-flex items-center gap-1 rounded-full border border-border-subtle bg-white px-2 py-0.5 text-xs text-text-muted transition-colors hover:border-primary/40 hover:text-teal-700"
      >
        <Icon name="book-open" size={12} aria-hidden="true" />
        Fuentes ({parrafo.sources.length})
      </button>
      {abierto && (
        <span
          id={idGlobo}
          role="tooltip"
          className="absolute right-0 top-full z-20 mt-1 block w-72 max-w-[calc(100vw-2rem)] rounded-lg border border-border-subtle bg-white p-3 text-left text-xs text-text-body shadow-lg"
        >
          <ContenidoFuentes parrafo={parrafo} />
        </span>
      )}
    </span>
  );
}

function Parrafo({ parrafo }: { parrafo: DraftParagraph }) {
  return (
    <div className="flex items-start gap-3 rounded-md px-3 py-2 text-sm leading-relaxed text-text-body hover:bg-warm-100/40">
      <p className="flex-1">
        <HighlightedText text={parrafo.text} />
      </p>
      <FuentesDelParrafo parrafo={parrafo} />
    </div>
  );
}

/**
 * Qué poner en una sección del documento técnico y la sugerencia de la IA para
 * esta licitación. Es una ayuda para quien edita: no se copia ni se exporta, por
 * eso va en cursiva y fuera de los párrafos seleccionables.
 */
function SugerenciaSeccion({ guidance, hint }: { guidance: string | null; hint: string | null }) {
  if (!guidance && !hint) return null;
  return (
    <div
      data-testid="sugerencia-seccion"
      className="mx-3 mt-1 mb-1 flex items-start gap-1.5 text-xs italic text-text-muted"
    >
      <Icon name="lightbulb" size={13} className="mt-0.5" aria-hidden="true" />
      <div>
        {guidance && <p>Qué poner: {guidance}</p>}
        {hint && <p>Para esta licitación: {hint}</p>}
      </div>
    </div>
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
  tenderCode = null,
  canWrite,
  busy,
  stage = null,
  onRegenerate,
  onDownload,
  onRequestTechnical,
}: ProposalDraftViewerProps) {
  const [regenerando, setRegenerando] = useState(false);
  const contenido = view.content;
  if (!contenido) return null;

  const secciones: { key: string; titulo: string; seccion: DraftSection }[] = [
    { key: "nombre", titulo: "Nombre de la oferta", seccion: contenido.offer_name },
    // Así se llama el campo en el formulario de Mercado Público.
    { key: "descripcion", titulo: "Detalle de la cotización", seccion: contenido.offer_description },
  ];
  // Mientras la IA reescribe, el texto de abajo ya no vale: se cubre para que
  // nadie lo copie, y se ve que algo está pasando aunque el aviso de etapa
  // quede lejos.
  const actualizando = stage === "drafting" || stage === "regenerating";

  return (
    <div>
      <NextSteps view={view} tenderCode={tenderCode} />
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-col gap-1 text-sm text-text-muted">
          <p>
            Copia cada sección al formulario de la Compra Ágil. Revisa lo resaltado antes de
            enviar.
          </p>
          <p className="flex items-center gap-1.5 text-xs">
            <Icon name="book-open" size={13} aria-hidden="true" />
            Para ver en qué dato de tu empresa se basa el texto, pasa el cursor o toca
            &quot;Fuentes&quot; en cada párrafo.
          </p>
        </div>
        {canWrite && !view.is_expired && (
          <Button
            variant="ghost"
            className="border border-border-strong"
            disabled={busy}
            isLoading={stage === "regenerating"}
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

      <div
        data-testid="contenido-borrador"
        aria-busy={actualizando || undefined}
        className="relative"
      >
        {actualizando && (
          // El aviso de etapa ya lo anuncia a los lectores de pantalla.
          <div
            data-testid="capa-de-carga"
            aria-hidden="true"
            className="absolute inset-0 z-10 flex items-start justify-center rounded-lg bg-white/70 pt-16 backdrop-blur-[1px]"
          >
            <span className="flex items-center gap-2 rounded-full border border-primary/20 bg-teal-50 px-4 py-2 text-sm font-semibold text-teal-700 shadow-md">
              <span className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
              {stage === "regenerating" ? "Regenerando el borrador…" : "Redactando el borrador…"}
            </span>
          </div>
        )}
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
                <Parrafo key={i} parrafo={p} />
              ))}
              {key === "descripcion" && <ContadorDetalle texto={textoDe(seccion)} />}
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

          {!contenido.technical_document && (
            // Sin veredicto: se muestra lo que dicen las bases y se ofrece como
            // opcional. En Compra Ágil el adjunto es optativo y puede reforzar la
            // cotización (guía del proveedor, paso 2).
            <section
              aria-label="Documento técnico"
              className="rounded-lg border border-border-subtle bg-white p-4 text-sm"
            >
              <h3 className="mb-1 flex items-center gap-2 text-sm font-bold text-text-strong">
                <Icon name="file-text" size={16} />
                Documento técnico (opcional)
              </h3>
              {view.technical_document_reason && (
                <p className="text-text-body">{view.technical_document_reason}</p>
              )}
              <p className="mt-1 text-text-muted">
                {view.technical_document_ambiguous
                  ? "Puedes adjuntar un documento técnico breve para reforzar tu cotización."
                  : "Un documento técnico breve que describa tu servicio puede reforzar la oferta."}
              </p>
              {canWrite && !view.is_expired && (
                <Button
                  variant={view.technical_document_ambiguous ? "primary" : "ghost"}
                  className={`mt-3 ${view.technical_document_ambiguous ? "" : "border border-border-strong"}`}
                  disabled={busy}
                  onClick={onRequestTechnical}
                >
                  <Icon name="file-plus" size={16} />
                  Generar documento técnico
                </Button>
              )}
            </section>
          )}

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
                  <SugerenciaSeccion guidance={s.guidance ?? null} hint={s.hint ?? null} />
                  {s.paragraphs.map((p, i) => (
                    <Parrafo key={i} parrafo={p} />
                  ))}
                </div>
              ))}
            </section>
          )}
        </div>

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
