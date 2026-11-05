"use client";

import { useEffect, useState, type ReactNode } from "react";
import { getTenderDetail } from "@/features/matches/services/tenderService";
import type { Tender } from "@/features/matches/tenderTypes";
import { QuotationEditor } from "@/features/quotations/QuotationEditor";
import { useTenderInteractionReporter } from "@/features/ranking-telemetry/hooks/useTenderInteractionReporter";
import { BackLink } from "@/features/shared/components/BackLink";
import { Button } from "@/features/shared/components/Button";
import { Dialog } from "@/features/shared/components/Dialog";
import { Icon } from "@/features/shared/components/Icon";
import { Toast } from "@/features/shared/components/Toast";
import { useTenderAttachments } from "@/features/tender-attachments/hooks/useTenderAttachments";
import { useCanWriteProposal } from "../hooks/useCanWriteProposal";
import { useProposal } from "../hooks/useProposal";
import { basesNotice, nombrarDocumentos, proposalStatus } from "../utils/proposal";
import { ChangedAnswersNotice } from "./ChangedAnswersNotice";
import { DiscrepancyModal } from "./DiscrepancyModal";
import { ExtensionPairingRequiredDialog } from "./ExtensionPairingRequiredDialog";
import { ExtensionRequiredDialog } from "./ExtensionRequiredDialog";
import { FeasibilityStep } from "./FeasibilityStep";
import { PostularEnMercadoPublicoButton } from "./PostularEnMercadoPublicoButton";
import { PostulationConfirmDialog } from "./PostulationConfirmDialog";
import { ProposalDraftViewer } from "./ProposalDraftViewer";
import { ProposalStatusBanner } from "./ProposalStatusBanner";
import { StageNotice } from "./StageNotice";
import { useMercadoPublicoPostulation } from "../hooks/useMercadoPublicoPostulation";

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
  // Los mismos anexos de la ficha que leen los hitos y el análisis (plan 233).
  const anexos = useTenderAttachments(tenderId);
  const canWrite = useCanWriteProposal();
  // Sin ranking del que venga la licitación: la interacción queda sin atribuir.
  const reportInteraction = useTenderInteractionReporter(tenderId, null);
  const [tender, setTender] = useState<{ data: Tender; isClosed: boolean } | null>(null);
  const [avisoAbierto, setAvisoAbierto] = useState(true);
  const [confirmarAnalisis, setConfirmarAnalisis] = useState(false);
  const [activeTab, setActiveTab] = useState<"cotizacion-borrador" | "postulacion">("cotizacion-borrador");

  const {
    busy: postulationBusy,
    packageData,
    showExtensionRequiredDialog,
    showConfirmDialog,
    startPostulation,
    confirm: handleConfirmPostulation,
    setShowExtensionRequiredDialog,
    setShowConfirmDialog,
    pairingRequired,
    pairAndContinue,
    retry: retryPostulation,
    postManually,
    setPairingRequired,
    error: postulationError,
    technicalDocxBase64,
  } = useMercadoPublicoPostulation({
    tenderId,
    tenderCode: tender?.data.code ?? null,
  });

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

  const { state, stage, busy, actionError, notice, answering, toast } = proposal;
  const view = state.kind === "ready" ? state.view : null;
  const cerrada = view?.is_expired ?? tender?.isClosed ?? false;
  const puedeAvanzar = canWrite && !cerrada;
  const estado = view ? proposalStatus(view) : null;
  // Con el nombre oficial: es el que el análisis guarda en `analysis_documents`.
  const anexosSubidos =
    anexos.state.status === "ready"
      ? anexos.state.data.official.filter((a) => a.file !== null).map((a) => a.name)
      : [];
  // Documentos oficiales que nadie subió: el aviso los nombra (#294).
  const anexosPendientes =
    anexos.state.status === "ready"
      ? anexos.state.data.official.filter((a) => a.file === null).map((a) => a.name)
      : [];
  const avisoBases = view ? basesNotice(view, anexosSubidos, anexosPendientes) : null;
  const sinBases = anexos.state.status === "ready" && anexosSubidos.length === 0;
  // Proyectos de experiencia: se ofrecen en el análisis, plegado o no.
  const evidencia = {
    onAddEvidence: proposal.addEvidence,
    suggestedEvidence: proposal.suggestedEvidence,
    onDismissEvidence: proposal.dismissEvidence,
  };

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

      {/*
        Avisos flotantes: el error, el aviso y la etapa en curso se ven desde
        cualquier parte de la página (por ejemplo, al regenerar desde el
        borrador). Van fijos y no con sticky porque el <main> del layout tiene
        overflow-auto sin altura fija: no se desplaza él, se desplaza la
        página, y un sticky dentro de él nunca se pega.
      */}
      <div className="pointer-events-none fixed inset-x-0 top-4 z-40 flex flex-col items-center gap-2 px-4">
        {actionError && (
          <div
            role="alert"
            className="pointer-events-auto flex w-full max-w-xl items-start justify-between gap-3 rounded-lg border border-danger/30 bg-danger-soft p-4 text-sm text-danger-text shadow-lg"
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
            className="pointer-events-auto flex w-full max-w-xl items-start justify-between gap-3 rounded-lg border border-primary/20 bg-primary-soft p-4 text-sm text-text-link shadow-lg"
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
      </div>

      {toast && (
        <Toast key={toast.id} message={toast.message} onClose={proposal.clearToast} />
      )}

      {view && estado && (
        <ProposalStatusBanner
          status={estado}
          canAct={puedeAvanzar}
          busy={busy}
          onResume={() => void proposal.resume()}
          onReview={() => setAvisoAbierto(true)}
        />
      )}

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
        <div className="rounded-lg border border-border-subtle bg-surface-card p-6 text-sm">
          <p className="mb-3 text-text-body">{state.message}</p>
          <Button onClick={() => void proposal.reload()}>Reintentar</Button>
        </div>
      )}

      {(state.kind === "not-started" || view || tender) && (
        <div
          role="tablist"
          aria-label="Pasos de la postulación"
          className="mb-6 flex overflow-x-auto whitespace-nowrap scrollbar-hide border-b border-border-subtle gap-8"
        >
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "cotizacion-borrador"}
            onClick={() => setActiveTab("cotizacion-borrador")}
            className={`shrink-0 whitespace-nowrap border-b-2 pb-3 text-sm transition-colors cursor-pointer ${
              activeTab === "cotizacion-borrador"
                ? "border-primary text-text-strong font-medium"
                : "border-transparent text-text-muted hover:text-text-strong"
            }`}
          >
            1. Cotización y Borrador
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "postulacion"}
            onClick={() => setActiveTab("postulacion")}
            className={`shrink-0 whitespace-nowrap border-b-2 pb-3 text-sm transition-colors cursor-pointer ${
              activeTab === "postulacion"
                ? "border-primary text-text-strong font-medium"
                : "border-transparent text-text-muted hover:text-text-strong"
            }`}
          >
            2. Postulación
          </button>
        </div>
      )}

      {activeTab === "cotizacion-borrador" && (
        <div className="flex flex-col gap-8">
          {(state.kind === "not-started" || view) && (
            <Seccion id="analisis" titulo="Análisis de las bases y exigencias">
              <div className="flex flex-col gap-5">
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border-subtle bg-surface-card p-4">
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
                  {puedeAvanzar && !view && sinBases && (
                    // Informativo y sin diálogo: iniciar sin bases es válido.
                    <p className="flex basis-full items-start gap-2 text-xs text-text-link">
                      <Icon name="info" size={14} className="mt-px shrink-0" />
                      {anexosPendientes.length > 0
                        ? `No has subido anexos. La Compra Ágil publica ${nombrarDocumentos(anexosPendientes)}: súbelos antes en los anexos para que el análisis salga más preciso. Puedes iniciar igual.`
                        : "No has subido anexos. Puedes iniciar igual, pero si la Compra Ágil tiene bases, súbelas antes en los anexos: el análisis sale más preciso."}
                    </p>
                  )}
                  {!canWrite && !view && (
                    <p className="text-sm text-text-muted">
                      Solo quienes pueden generar postulaciones en esta empresa pueden
                      iniciarla.
                    </p>
                  )}
                </div>

                {view &&
                  (view.status === "READY" ? (
                    <details className="rounded-lg border border-border-subtle bg-surface-card p-4">
                      <summary className="cursor-pointer text-sm font-semibold text-text-strong">
                        Ver exigencias evaluadas ({view.requirements.length})
                      </summary>
                      <div className="mt-4">
                        <FeasibilityStep
                          view={view}
                          canWrite={canWrite}
                          busy={busy}
                          answering={answering}
                          onAnswer={(questionId, label) => void proposal.answer(questionId, label)}
                          onGenerate={() => void proposal.generate()}
                          {...evidencia}
                        />
                      </div>
                    </details>
                  ) : (
                    <FeasibilityStep
                      view={view}
                      canWrite={canWrite}
                      busy={busy}
                      answering={answering}
                      onAnswer={(questionId, label) => void proposal.answer(questionId, label)}
                      onGenerate={() => void proposal.generate()}
                      {...evidencia}
                    />
                  ))}
              </div>
            </Seccion>
          )}

          {tender && (
            <Seccion id="cotizacion" titulo="Cotización de materiales">
              <QuotationEditor
                tenderId={tenderId}
                tenderCode={tender.data.code}
                tenderItems={tender.data.items}
                onSaved={() => reportInteraction("cotizacion")}
                defaultOpen={true}
              />
            </Seccion>
          )}

          {view && (
            <Seccion id="borrador" titulo="Borrador de la oferta">
              {avisoBases && (
                <p className="mb-5 flex items-start gap-2 rounded-lg border border-primary/20 bg-primary-soft p-4 text-sm text-text-link">
                  <Icon name="info" size={16} className="mt-0.5 shrink-0" />
                  <span>{avisoBases}</span>
                </p>
              )}
              {view.content ? (
                <ProposalDraftViewer
                  view={view}
                  tenderCode={tender?.data.code ?? null}
                  canWrite={canWrite}
                  busy={busy}
                  stage={stage}
                  onRegenerate={(instrucciones) => void proposal.regenerate(instrucciones)}
                  onDownload={() => void proposal.download()}
                  onRequestTechnical={() => void proposal.requestTechnical()}
                  showPostulateButton={false}
                  onContinueToPostulation={() => setActiveTab("postulacion")}
                />
              ) : (
                <p className="rounded-lg border border-dashed border-border-default bg-surface-card p-6 text-sm text-text-muted">
                  {estado?.detail ?? 'Cuando quieras, usa "Redactar borrador" en el análisis.'}
                </p>
              )}
            </Seccion>
          )}
        </div>
      )}

      {activeTab === "postulacion" && (
        <Seccion id="postulacion" titulo="Postulación en Mercado Público">
          <div className="rounded-lg border border-border-subtle bg-surface-card p-6">
            <div className="mb-6 flex flex-col gap-1">
              <h3 className="text-base font-bold text-text-strong">
                Postulación asistida con Extensión oficial de Chiripa
              </h3>
              <p className="text-sm text-text-muted">
                Transfiere tu cotización y propuesta redactada directamente a la ficha oficial de Mercado Público.
              </p>
            </div>

            {view?.content ? (
              <div className="flex flex-col gap-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 rounded-lg border border-border-subtle bg-surface-inset p-4 text-sm">
                  <div>
                    <span className="text-xs font-semibold uppercase tracking-wider text-text-muted">
                      Licitación
                    </span>
                    <p className="font-bold text-text-strong">{tender?.data.code ?? view.tender_id}</p>
                    <p className="text-xs text-text-muted">{tender?.data.name ?? "Sin nombre"}</p>
                  </div>
                  <div>
                    <span className="text-xs font-semibold uppercase tracking-wider text-text-muted">
                      Propuesta redactada
                    </span>
                    <p className="font-bold text-text-strong">
                      {view.content.offer_name.paragraphs[0]?.text || "Oferta estándar"}
                    </p>
                    <p className="line-clamp-2 text-xs text-text-muted">
                      {view.content.offer_description.paragraphs[0]?.text || "Sin descripción"}
                    </p>
                  </div>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-primary/20 bg-primary-soft/30 p-4">
                  <div>
                    <p className="text-sm font-semibold text-text-strong">
                      ¿Todo listo para cargar en Mercado Público?
                    </p>
                    <p className="text-xs text-text-muted">
                      Al presionar el botón se abrirá la ventana de confirmación previa para verificar precios finales antes de cargarlos.
                    </p>
                  </div>
                  <PostularEnMercadoPublicoButton
                    canWrite={puedeAvanzar}
                    isExpired={cerrada}
                    busy={postulationBusy || busy}
                    onClick={startPostulation}
                  />
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center gap-4 py-8 text-center">
                <Icon name="file-text" size={40} className="text-text-muted" />
                <div className="max-w-md">
                  <p className="font-semibold text-text-strong">
                    Aún no se ha redactado el borrador de la oferta
                  </p>
                  <p className="mt-1 text-sm text-text-muted">
                    Para postular con la extensión, primero debes completar la cotización y generar el borrador en el paso 1.
                  </p>
                </div>
                <Button onClick={() => setActiveTab("cotizacion-borrador")}>
                  Ir al Paso 1: Cotización y Borrador
                </Button>
              </div>
            )}
          </div>
        </Seccion>
      )}

      <ExtensionPairingRequiredDialog
        open={Boolean(pairingRequired)}
        busy={postulationBusy}
        error={postulationError ?? null}
        onPair={() => void pairAndContinue()}
        onRetry={() => void retryPostulation()}
        onPostManually={postManually}
        onClose={() => setPairingRequired(false)}
      />
      <ExtensionRequiredDialog
        open={showExtensionRequiredDialog}
        onClose={() => setShowExtensionRequiredDialog(false)}
      />

      <PostulationConfirmDialog
        open={showConfirmDialog}
        packageData={packageData}
        busy={postulationBusy}
        onClose={() => setShowConfirmDialog(false)}
        onConfirm={handleConfirmPostulation}
        technicalDocxBase64={technicalDocxBase64}
      />

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
