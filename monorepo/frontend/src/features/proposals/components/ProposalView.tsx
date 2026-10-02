"use client";

import { useEffect, useState, type ReactNode } from "react";
import { getTenderDetail } from "@/features/matches/services/tenderService";
import type { Tender } from "@/features/matches/tenderTypes";
import { QuotationEditor } from "@/features/quotations/QuotationEditor";
import { BackLink } from "@/features/shared/components/BackLink";
import { Button } from "@/features/shared/components/Button";
import { Dialog } from "@/features/shared/components/Dialog";
import { Icon } from "@/features/shared/components/Icon";
import { useCanWriteProposal } from "../hooks/useCanWriteProposal";
import { useProposal } from "../hooks/useProposal";
import { pendingRequirements } from "../utils/proposal";
import { ChangedAnswersNotice } from "./ChangedAnswersNotice";
import { DiscrepancyModal } from "./DiscrepancyModal";
import { FeasibilityStep } from "./FeasibilityStep";
import { ProposalAttachments } from "./ProposalAttachments";
import { ProposalDraftViewer } from "./ProposalDraftViewer";
import { StageNotice } from "./StageNotice";

interface ProposalViewProps {
  tenderId: string;
}

function Seccion({
  id,
  titulo,
  children,
}: {
  id: string;
  titulo: string;
  children: ReactNode;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-titulo`} className="mb-8 scroll-mt-6">
      <h2 id={`${id}-titulo`} className="mb-4 font-display text-lg font-bold text-text-strong">
        {titulo}
      </h2>
      {children}
    </section>
  );
}

/**
 * Postulación a una Compra Ágil (HU-20), en una sola página y sin pasos: el
 * análisis de las bases, el borrador y la cotización quedan a la vista, y se
 * puede volver a analizar en cualquier momento (por ejemplo, tras subir las
 * bases que faltaban).
 */
export function ProposalView({ tenderId }: ProposalViewProps) {
  const proposal = useProposal(tenderId);
  const canWrite = useCanWriteProposal();
  const [tender, setTender] = useState<{ data: Tender; isClosed: boolean } | null>(null);
  const [avisoAbierto, setAvisoAbierto] = useState(true);
  const [confirmarAnalisis, setConfirmarAnalisis] = useState(false);

  useEffect(() => {
    let cancelado = false;
    getTenderDetail(tenderId)
      .then((detalle) => {
        if (!cancelado) setTender({ data: detalle.tender, isClosed: detalle.is_closed });
      })
      .catch(() => {
        // La ficha es el encabezado y el cotizador: sin ella el resto funciona.
      });
    return () => {
      cancelado = true;
    };
  }, [tenderId]);

  const { state, stage, busy, actionError, notice } = proposal;
  const view = state.kind === "ready" ? state.view : null;
  const cerrada = view?.is_expired ?? tender?.isClosed ?? false;
  const puedeAvanzar = canWrite && !cerrada;

  const volverAAnalizar = () => {
    // Con texto redactado se pide confirmación: si hubo cambios, se descarta.
    if (view?.content) setConfirmarAnalisis(true);
    else void proposal.reanalyze();
  };

  return (
    <section className="mx-auto w-full max-w-5xl">
      <BackLink fallbackHref={`/matches/${tenderId}`}>Volver a la licitación</BackLink>

      <header className="mb-6">
        <p className="text-xs font-semibold uppercase tracking-wide text-text-subtle">
          Postulación {tender ? `· ${tender.data.code}` : ""}
        </p>
        <h1 className="font-display text-2xl font-bold text-text-strong">
          {tender?.data.name ?? "Postulación"}
        </h1>
      </header>

      {cerrada && (
        <div
          role="alert"
          className="mb-6 rounded-lg border border-warning/30 bg-warning-soft/40 p-4 text-sm text-text-body"
        >
          Esta licitación se encuentra cerrada para postulaciones. Puedes revisar lo que se
          generó, pero no avanzar.
        </div>
      )}

      {actionError && (
        <div
          role="alert"
          className="mb-6 flex items-start justify-between gap-3 rounded-lg border border-danger/30 bg-danger-soft/40 p-4 text-sm text-red-700"
        >
          <span>{actionError}</span>
          <button
            type="button"
            className="text-xs font-semibold underline"
            onClick={proposal.clearActionError}
          >
            Cerrar
          </button>
        </div>
      )}

      {notice && (
        <div
          role="status"
          className="mb-6 flex items-start justify-between gap-3 rounded-lg border border-primary/20 bg-teal-50/60 p-4 text-sm text-teal-700"
        >
          <span>{notice}</span>
          <button
            type="button"
            className="text-xs font-semibold underline"
            onClick={proposal.clearNotice}
          >
            Cerrar
          </button>
        </div>
      )}

      <StageNotice stage={stage} />

      {view && (
        <ChangedAnswersNotice
          view={view}
          canWrite={puedeAvanzar}
          busy={busy}
          onSync={() => void proposal.syncAnswers()}
        />
      )}

      {state.kind === "loading" && (
        <p className="text-sm text-text-muted">Cargando postulación…</p>
      )}

      {state.kind === "error" && (
        <div className="rounded-lg border border-border-subtle bg-white p-6 text-sm">
          <p className="mb-3 text-text-body">{state.message}</p>
          <Button onClick={() => void proposal.reload()}>Reintentar</Button>
        </div>
      )}

      {(state.kind === "not-started" || view) && (
        <Seccion id="analisis" titulo="Análisis de las bases">
          <div className="grid gap-5 lg:grid-cols-[1fr_20rem]">
            <div className="flex flex-col gap-5">
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border-subtle bg-white p-4">
                <p className="text-sm text-text-body">
                  {view
                    ? "Si subiste bases nuevas o cambiaste el perfil de tu empresa, vuelve a analizar."
                    : "Cruzamos las bases con el perfil de tu empresa. Si falta algún dato, te lo preguntamos."}
                </p>
                {puedeAvanzar &&
                  (view ? (
                    <Button
                      variant="ghost"
                      className="border border-border-strong"
                      disabled={busy}
                      onClick={volverAAnalizar}
                    >
                      <Icon name="refresh-cw" size={16} />
                      Volver a analizar
                    </Button>
                  ) : (
                    <Button
                      onClick={() => void proposal.start()}
                      disabled={busy}
                      isLoading={busy}
                    >
                      <Icon name="sparkles" size={16} />
                      Iniciar análisis
                    </Button>
                  ))}
                {!canWrite && !view && (
                  <p className="text-sm text-text-muted">
                    Solo quienes pueden generar postulaciones en esta empresa pueden
                    iniciarla.
                  </p>
                )}
              </div>

              {view && view.status === "STOPPED" && (
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border-strong bg-warm-100/60 p-4 text-sm">
                  <span>
                    <strong>Postulación detenida.</strong> Al reanudar puedes corregir la
                    respuesta que la detuvo.
                  </span>
                  {puedeAvanzar && (
                    <Button onClick={() => void proposal.resume()} disabled={busy}>
                      Reanudar
                    </Button>
                  )}
                </div>
              )}

              {view && view.status === "PAUSED" && !avisoAbierto && (
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-danger/30 bg-danger-soft/30 p-4 text-sm">
                  <span>Hay una exigencia excluyente que la empresa declaró no cumplir.</span>
                  <Button onClick={() => setAvisoAbierto(true)}>Revisar</Button>
                </div>
              )}

              {view &&
                (view.status === "READY" ? (
                  <details className="rounded-lg border border-border-subtle bg-white p-4">
                    <summary className="cursor-pointer text-sm font-semibold text-text-strong">
                      Ver exigencias evaluadas ({view.requirements.length})
                    </summary>
                    <div className="mt-4">
                      <FeasibilityStep
                        view={view}
                        canWrite={canWrite}
                        busy={busy}
                        onAnswer={(questionId, label) => void proposal.answer(questionId, label)}
                        onGenerate={() => void proposal.generate()}
                      />
                    </div>
                  </details>
                ) : (
                  <FeasibilityStep
                    view={view}
                    canWrite={canWrite}
                    busy={busy}
                    onAnswer={(questionId, label) => void proposal.answer(questionId, label)}
                    onGenerate={() => void proposal.generate()}
                  />
                ))}
            </div>
            <ProposalAttachments tenderId={tenderId} />
          </div>
        </Seccion>
      )}

      {view && (
        <Seccion id="borrador" titulo="Borrador de la oferta">
          {view.content ? (
            <ProposalDraftViewer
              view={view}
              tenderCode={tender?.data.code ?? null}
              canWrite={canWrite}
              busy={busy}
              onRegenerate={(instrucciones) => void proposal.regenerate(instrucciones)}
              onDownload={() => void proposal.download()}
              onRequestTechnical={() => void proposal.requestTechnical()}
            />
          ) : (
            <p className="rounded-lg border border-dashed border-border-default bg-white p-6 text-sm text-text-muted">
              {pendingRequirements(view).length > 0
                ? "Responde las preguntas del análisis y luego redacta el borrador."
                : "Cuando quieras, usa “Redactar borrador” en el análisis."}
            </p>
          )}
        </Seccion>
      )}

      {tender && (
        <Seccion id="cotizacion" titulo="Cotización">
          <QuotationEditor
            tenderId={tenderId}
            tenderCode={tender.data.code}
            tenderItems={tender.data.items}
          />
        </Seccion>
      )}

      {view && (
        <DiscrepancyModal
          view={view}
          open={avisoAbierto && view.status === "PAUSED"}
          busy={busy}
          canWrite={puedeAvanzar}
          onClose={() => setAvisoAbierto(false)}
          onUpdateAnswer={(questionId, label) => void proposal.answer(questionId, label)}
          onDecide={(requirementId, action) => void proposal.decide(requirementId, action)}
        />
      )}

      <Dialog
        open={confirmarAnalisis}
        title="¿Volver a analizar las bases?"
        onClose={() => setConfirmarAnalisis(false)}
      >
        <p className="text-sm text-text-body">
          Si subiste bases nuevas o cambiaste el perfil de tu empresa, se rehará el análisis y
          el borrador redactado se descartará para redactarlo de nuevo. Tus respuestas se
          mantienen. Si no hubo cambios, el borrador queda como está.
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setConfirmarAnalisis(false)}>
            Cancelar
          </Button>
          <Button
            onClick={() => {
              setConfirmarAnalisis(false);
              void proposal.reanalyze();
            }}
          >
            Volver a analizar
          </Button>
        </div>
      </Dialog>
    </section>
  );
}
