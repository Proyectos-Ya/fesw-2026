"use client";

import { useEffect, useState } from "react";
import { getTenderDetail } from "@/features/matches/services/tenderService";
import { BackLink } from "@/features/shared/components/BackLink";
import { Button } from "@/features/shared/components/Button";
import { Icon } from "@/features/shared/components/Icon";
import type { Tender } from "@/features/matches/tenderTypes";
import { useCanWriteProposal } from "../hooks/useCanWriteProposal";
import { useProposal } from "../hooks/useProposal";
import { DiscrepancyModal } from "./DiscrepancyModal";
import { FeasibilityStep } from "./FeasibilityStep";
import { ProposalAttachments } from "./ProposalAttachments";
import { ProposalDraftViewer } from "./ProposalDraftViewer";
import { ProposalStepper } from "./ProposalStepper";

interface ProposalViewProps {
  tenderId: string;
}

/**
 * Pestaña de la postulación a una Compra Ágil (HU-20).
 *
 * Fase 1, factibilidad: preguntas y discrepancias. Fase 2, redacción: el
 * borrador para copiar al formulario y, si las bases lo exigen, el documento
 * técnico en Word.
 */
export function ProposalView({ tenderId }: ProposalViewProps) {
  const proposal = useProposal(tenderId);
  const canWrite = useCanWriteProposal();
  const [tender, setTender] = useState<{ data: Tender; isClosed: boolean } | null>(null);
  const [avisoAbierto, setAvisoAbierto] = useState(true);

  useEffect(() => {
    let cancelado = false;
    getTenderDetail(tenderId)
      .then((detalle) => {
        if (!cancelado) setTender({ data: detalle.tender, isClosed: detalle.is_closed });
      })
      .catch(() => {
        // La ficha es solo el encabezado: sin ella la postulación igual funciona.
      });
    return () => {
      cancelado = true;
    };
  }, [tenderId]);

  const { state, stage, busy, actionError } = proposal;
  const view = state.kind === "ready" ? state.view : null;
  const cerrada = view?.is_expired ?? tender?.isClosed ?? false;

  return (
    <section className="mx-auto w-full max-w-5xl">
      <BackLink fallbackHref={`/matches/${tenderId}`}>Volver a la licitación</BackLink>

      <header className="mb-6">
        <p className="text-xs font-semibold uppercase tracking-wide text-text-subtle">
          Postulación {tender ? `· ${tender.data.code}` : ""}
        </p>
        <h1 className="font-display text-2xl font-bold text-text-strong">
          {tender?.data.name ?? "Generar postulación"}
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

      <ProposalStepper status={view?.status ?? null} stage={stage} />

      {state.kind === "loading" && (
        <p className="text-sm text-text-muted">Cargando postulación…</p>
      )}

      {state.kind === "error" && (
        <div className="rounded-lg border border-border-subtle bg-white p-6 text-sm">
          <p className="mb-3 text-text-body">{state.message}</p>
          <Button variant="primary" onClick={() => void proposal.reload()}>
            Reintentar
          </Button>
        </div>
      )}

      {state.kind === "not-started" && (
        <div className="grid gap-5 lg:grid-cols-[1fr_20rem]">
          <div className="rounded-lg border border-border-subtle bg-white p-6">
            <h2 className="mb-2 text-lg font-bold text-text-strong">
              Prepara tu postulación con IA
            </h2>
            <ol className="mb-5 list-decimal pl-5 text-sm text-text-body">
              <li>
                Analizamos las bases y las cruzamos con el perfil de tu empresa. Si falta
                algún dato, te lo preguntamos.
              </li>
              <li>
                Redactamos el nombre y la descripción de la oferta y la lista de documentos
                a adjuntar, y el documento técnico si las bases lo exigen.
              </li>
            </ol>
            {canWrite ? (
              <Button
                onClick={() => void proposal.start()}
                disabled={cerrada || busy}
                isLoading={busy}
              >
                <Icon name="sparkles" size={16} />
                Iniciar análisis de factibilidad
              </Button>
            ) : (
              <p className="text-sm text-text-muted">
                Solo quienes pueden generar postulaciones en esta empresa pueden iniciarla.
              </p>
            )}
          </div>
          <ProposalAttachments tenderId={tenderId} />
        </div>
      )}

      {view && view.status === "STOPPED" && (
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border-strong bg-warm-100/60 p-4 text-sm">
          <span>
            <strong>Postulación detenida.</strong> Al reanudar puedes corregir la respuesta
            que la detuvo.
          </span>
          {canWrite && !cerrada && (
            <Button onClick={() => void proposal.resume()} disabled={busy}>
              Reanudar
            </Button>
          )}
        </div>
      )}

      {view && view.status === "PAUSED" && !avisoAbierto && (
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-danger/30 bg-danger-soft/30 p-4 text-sm">
          <span>Hay una exigencia excluyente que la empresa declaró no cumplir.</span>
          <Button onClick={() => setAvisoAbierto(true)}>
            Revisar
          </Button>
        </div>
      )}

      {view && view.status !== "READY" && (
        <div className="grid gap-5 lg:grid-cols-[1fr_20rem]">
          <FeasibilityStep
            view={view}
            canWrite={canWrite}
            busy={busy}
            onAnswer={(questionId, label) => void proposal.answer(questionId, label)}
            onGenerate={() => void proposal.generate()}
          />
          <ProposalAttachments tenderId={tenderId} />
        </div>
      )}

      {view && view.status === "READY" && (
        <ProposalDraftViewer
          view={view}
          tenderCode={tender?.data.code ?? null}
          canWrite={canWrite}
          busy={busy}
          onRegenerate={(instrucciones) => void proposal.regenerate(instrucciones)}
          onDownload={() => void proposal.download()}
        />
      )}

      {view && (
        <DiscrepancyModal
          view={view}
          open={avisoAbierto && view.status === "PAUSED"}
          busy={busy}
          canWrite={canWrite && !cerrada}
          onClose={() => setAvisoAbierto(false)}
          onUpdateAnswer={(questionId, label) => void proposal.answer(questionId, label)}
          onDecide={(requirementId, action) => void proposal.decide(requirementId, action)}
        />
      )}
    </section>
  );
}
