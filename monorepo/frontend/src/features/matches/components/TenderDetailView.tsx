"use client";

/* eslint-disable react-hooks/set-state-in-effect -- bootstrap fetch uses the canonical effect+cancel pattern. */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/features/auth/AuthContext";
import { ApiError, TimeoutError } from "@/features/shared/api/client";
import { Badge, type BadgeTone } from "@/features/shared/components/Badge";
import { BackLink } from "@/features/shared/components/BackLink";
import { Button } from "@/features/shared/components/Button";
import { Icon } from "@/features/shared/components/Icon";
import { MatchMeter } from "@/features/shared/components/MatchMeter";
import {
  calculateTenderScore,
  generateDeepAnalysis,
  getRecommendedTenders,
  getDeepAnalysisOnly,
  getTenderDetail,
} from "../services/tenderService";
import {
  fetchSavedTenders,
  saveTenderApi,
  unsaveTenderApi,
} from "@/features/saved-tenders/services/savedTenders.service";
import { getSaveErrorMessage } from "@/features/saved-tenders/constants";
import type { MatchingResult, Tender, DeepAnalysis } from "../tenderTypes";
import { compraAgilFichaUrl } from "../utils/links";
import { TenderAssistantDrawer } from "@/features/tender-assistant/components/TenderAssistantDrawer";
import { QuotationEditor } from "@/features/quotations/QuotationEditor";
import {
  daysUntilClosing,
  formatCLP,
  formatClosingDate,
  formatDateTime,
  normalizeScore,
  type ClosingTone,
} from "../utils/format";


interface TenderDetailViewProps {
  tenderId: string;
}

type LoadState =
  | { kind: "idle" }
  | { kind: "loading" }
  | {
      kind: "ready";
      match: MatchingResult;
      isClosed: boolean;
      /** Viene del top-N: su puntaje lo mantiene al día el propio ranking. */
      isRecommended: boolean;
    }
  | { kind: "not-found" }
  | { kind: "error"; message: string };

/** Qué acción de IA está en curso, para no permitir dos a la vez. */
type PendingAction = "score" | "analysis" | null;

const DETAIL_THRESHOLDS = { high: 70, mid: 40 };
const DETAIL_COLORS = {
  high: "var(--green-500)",
  mid: "var(--amber-500)",
  low: "var(--red-500)",
};

function closingBadgeTone(tone: ClosingTone): BadgeTone {
  switch (tone) {
    case "danger":
      return "danger";
    case "warning":
      return "warning";
    case "expired":
      return "neutral";
    default:
      return "neutral";
  }
}

function scoreLabel(score: number): string {
  if (score >= 70) return "Alta compatibilidad";
  if (score >= 40) return "Compatibilidad media";
  return "Baja compatibilidad";
}

export function TenderDetailView({ tenderId }: TenderDetailViewProps) {
  const router = useRouter();
  const { user, isLoading: authLoading, isAuthenticated } = useAuth();
  const [state, setState] = useState<LoadState>({ kind: "idle" });
  const [analysis, setAnalysis] = useState<DeepAnalysis | null>(null);
  // El puntaje vive aparte del estado de carga: el usuario puede calcularlo o
  // recalcularlo sin volver a pedir la licitación entera.
  const [score, setScore] = useState<number | null>(null);
  const [pendingAction, setPendingAction] = useState<PendingAction>(null);
  const [retryNonce, setRetryNonce] = useState(0);
  const [isAssistantOpen, setIsAssistantOpen] = useState(false);
  const [isSaved, setIsSaved] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);



  useEffect(() => {
    if (authLoading) return;
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }
    if (!user) return;

    let cancelled = false;
    setState({ kind: "loading" });
    setAnalysis(null);
    setScore(null);

    void (async () => {
      try {
        const [matches, savedList] = await Promise.all([
          getRecommendedTenders(user.id),
          fetchSavedTenders().catch(() => []),
        ]);

        if (cancelled) return;

        // Vale para los dos caminos de abajo: una licitación cerrada también
        // puede estar guardada, así que esto no depende de las recomendaciones.
        setIsSaved(
          savedList.some(
            (item) => (item.tender?.id ?? item.tender_id ?? item.id) === tenderId
          )
        );

        const found = matches.find((m) => m.tender?.id === tenderId);
        if (found) {
          setScore(
            found.final_score !== null ? normalizeScore(found.final_score) : null
          );
          setState({
            kind: "ready",
            match: found,
            isClosed: false,
            isRecommended: true,
          });
        } else {
          // Las recomendaciones descartan lo que ya cerró, así que no encontrarla
          // ahí no significa que no exista: puede ser una alerta de hace días.
          // El detalle directo sí la devuelve, marcada como cerrada.
          const detalle = await getTenderDetail(tenderId);
          if (cancelled) return;
          // `score_pct` en nulo significa "nadie lo ha calculado", no "cero":
          // el ranking solo puntúa sus doce mejores.
          setScore(detalle.score_pct ?? null);
          setState({
            kind: "ready",
            isClosed: detalle.is_closed,
            isRecommended: false,
            match: {
              id: detalle.tender.id,
              supplier_id: "",
              tender_id: detalle.tender.id,
              similarity_score: null,
              reranker_score: null,
              final_score:
                detalle.score_pct !== null ? detalle.score_pct / 100 : null,
              model_version: "",
              calculated_at: detalle.tender.updated_at,
              tender: detalle.tender,
            },
          });
        }

        // Cargar el análisis de compatibilidad si ya existe
        try {
          const ana = await getDeepAnalysisOnly(tenderId);
          if (!cancelled) {
            setAnalysis(ana);
          }
        } catch (err) {
          console.error("Error al cargar análisis de compatibilidad:", err);
        }
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) {
          setState({ kind: "not-found" });
          return;
        }
        if (err instanceof ApiError || err instanceof TimeoutError) {
          setState({ kind: "error", message: err.message });
          return;
        }
        setState({
          kind: "error",
          message: "No pudimos cargar el detalle de la licitación.",
        });
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [authLoading, isAuthenticated, user, router, tenderId, retryNonce]);

  const handleCalculateScore = async () => {
    setActionError(null);
    setPendingAction("score");
    try {
      const resultado = await calculateTenderScore(tenderId);
      setScore(resultado.score_pct);
      // Si el número se movió, la justificación guardada quedó explicando otro
      // puntaje. Se marca desactualizada en vez de dejar dos cifras distintas
      // en la misma pantalla.
      if (analysis && Math.round(analysis.compatibility_score) !== resultado.score_pct) {
        setAnalysis({ ...analysis, is_outdated: true });
      }
    } catch (err) {
      console.error("Error al calcular la compatibilidad:", err);
      setActionError(
        err instanceof ApiError
          ? err.message
          : "No pudimos calcular la compatibilidad. Inténtalo de nuevo."
      );
    } finally {
      setPendingAction(null);
    }
  };

  const handleRegenerateAnalysis = async () => {
    setActionError(null);
    setPendingAction("analysis");
    try {
      const actualizado = await generateDeepAnalysis(tenderId, undefined, true);
      setAnalysis(actualizado);
      setScore(Math.round(actualizado.compatibility_score));
    } catch (err) {
      console.error("Error al actualizar el análisis:", err);
      setActionError(
        err instanceof ApiError
          ? err.message
          : "No pudimos actualizar el análisis. Inténtalo de nuevo."
      );
    } finally {
      setPendingAction(null);
    }
  };

  const handleToggleSave = async () => {
    const previousState = isSaved;
    setActionError(null);
    setIsSaved(!previousState);

    try {
      if (previousState) {
        await unsaveTenderApi(tenderId);
      } else {
        await saveTenderApi(tenderId);
      }
    } catch (err) {
      console.error("Error al actualizar guardado:", err);
      setIsSaved(previousState);
      setActionError(getSaveErrorMessage(previousState));
    }
  };

  if (authLoading || state.kind === "idle" || state.kind === "loading") {
    return (
      <section className="mx-auto w-full max-w-4xl">
        <BackLink fallbackHref="/matches">Volver</BackLink>
        <div className="rounded-lg border border-border-subtle bg-surface-card p-10 text-center text-sm text-text-muted">
          Cargando detalle…
        </div>
      </section>
    );
  }

  if (state.kind === "not-found") {
    return (
      <section className="mx-auto w-full max-w-4xl">
        <BackLink fallbackHref="/matches">Volver</BackLink>
        <div className="rounded-lg border border-border-subtle bg-surface-card p-10 text-center shadow-xs">
          <h2 className="font-display text-xl font-semibold text-text-strong">
            No encontramos esta licitación
          </h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-text-muted">
            Es posible que ya no esté entre tus matches recomendados o que el enlace
            esté desactualizado.
          </p>
        </div>
      </section>
    );
  }

  if (state.kind === "error") {
    return (
      <section className="mx-auto w-full max-w-4xl">
        <BackLink fallbackHref="/matches">Volver</BackLink>
        <div className="rounded-lg border border-danger/20 bg-danger-soft/30 p-6 text-center">
          <p className="text-sm font-medium text-danger">{state.message}</p>
          <Button
            variant="primary"
            className="mt-4"
            onClick={() => setRetryNonce((n) => n + 1)}
          >
            Reintentar
          </Button>
        </div>
      </section>
    );
  }

  const { match } = state;
  const tender = match.tender as Tender;
  const closing = daysUntilClosing(tender.closing_at);
  const buyer = tender.buyer_name ?? "Organismo no especificado";
  const officialUrl = compraAgilFichaUrl(tender.code);
  // El backend ya evalúa estado y fecha de cierre; `closing` cubre el caso de
  // una ficha abierta desde los matches cuyo plazo venció mientras se miraba.
  const cerrada = state.isClosed || closing.tone === "expired";

  return (
    <section className="mx-auto w-full max-w-4xl">
      <BackLink fallbackHref="/matches">Volver</BackLink>

      {/* Criterio de la HdU 08: al abrir la alerta de una licitación cuyo plazo
          ya pasó, hay que decirlo en vez de mostrar la ficha como si siguiera
          disponible. */}
      {cerrada && (
        <div
          role="alert"
          className="mb-6 flex items-start gap-3 rounded-lg border border-warning/30 bg-warning-soft/40 p-4"
        >
          <Icon name="triangle-alert" size={18} color="var(--amber-500)" />
          <div>
            <p className="text-sm font-semibold text-text-strong">
              Esta licitación ya cerró
            </p>
            <p className="mt-1 text-sm text-text-body">
              El plazo de postulación venció el{" "}
              {formatClosingDate(tender.closing_at)}. Es posible que ya haya sido
              adjudicada; puedes revisar su estado oficial en Mercado Público.
            </p>
          </div>
        </div>
      )}

      {actionError && (
        <div
          role="alert"
          className="mb-4 flex items-center justify-between rounded-md border border-danger/20 bg-danger-soft/30 p-4 text-sm font-medium text-danger"
        >
          <span>{actionError}</span>
          <button
            type="button"
            onClick={() => setActionError(null)}
            className="text-xs font-bold underline hover:opacity-80 cursor-pointer ml-4"
          >
            Cerrar
          </button>
        </div>
      )}

      <header className="mb-6 flex flex-col gap-5 rounded-lg border border-border-subtle bg-surface-card p-6 shadow-xs sm:flex-row sm:items-start">
        <div className="flex-none sm:w-28">
          {score !== null ? (
            <>
              <MatchMeter
                value={score}
                size="lg"
                thresholds={DETAIL_THRESHOLDS}
                colors={DETAIL_COLORS}
              />
              <div className="mt-2 text-center text-[10px] font-bold uppercase tracking-caps text-text-subtle">
                {scoreLabel(score)}
              </div>
            </>
          ) : (
            /* Sin puntaje no es lo mismo que cero: el ranking solo calcula sus
               doce mejores, y el resto se mide cuando el usuario lo pide. */
            <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border-strong p-4 text-center">
              <Icon name="gauge" size={22} color="var(--text-subtle)" />
              <span className="mt-1 text-[10px] font-bold uppercase tracking-caps text-text-subtle">
                Sin puntaje
              </span>
            </div>
          )}

          {/* En una recomendada no se ofrece recalcular: ese puntaje lo
              refresca el ranking, y rehacerlo acá la sacaría del dashboard. */}
          {!cerrada && !state.isRecommended && (
            <Button
              variant="ghost"
              onClick={handleCalculateScore}
              disabled={pendingAction !== null}
              className="mt-2 w-full border border-border-strong bg-white text-xs hover:bg-slate-50"
              id="btn-calculate-score"
            >
              {pendingAction === "score" ? (
                <span className="inline-flex items-center gap-1.5">
                  <Icon name="loader-circle" className="animate-spin" size={13} />
                  Calculando…
                </span>
              ) : score !== null ? (
                "Recalcular"
              ) : (
                "Calcular compatibilidad"
              )}
            </Button>
          )}
        </div>

        <div className="min-w-0 flex-1">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <Badge tone="teal">Compra Ágil</Badge>
            <Badge tone={closingBadgeTone(closing.tone)} dot={closing.tone === "danger"}>
              {closing.label}
            </Badge>
            <span className="font-mono text-xs text-text-subtle">ID {tender.code}</span>

            <div className="flex-1" />

            <button
              type="button"
              onClick={handleToggleSave}
              aria-label={isSaved ? "Quitar de licitaciones guardadas" : "Guardar licitación"}
              title={isSaved ? "Quitar de guardadas" : "Guardar licitación"}
              className={`inline-flex size-9 items-center justify-center rounded-full transition-all duration-200 cursor-pointer ${
                isSaved
                  ? "bg-primary-soft text-primary hover:bg-teal-100 hover:scale-105 active:scale-95"
                  : "text-text-subtle hover:bg-surface-hover hover:text-primary hover:scale-105 active:scale-95"
              } focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40`}
            >
              <Icon
                name={isSaved ? "bookmark-check" : "bookmark"}
                size={19}
                color={isSaved ? "var(--primary)" : "currentColor"}
              />
            </button>
          </div>

          <h1 className="font-display text-3xl font-bold leading-tight tracking-tight text-text-strong">
            {tender.name}
          </h1>

          <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-text-muted">
            <span className="inline-flex items-center gap-1.5">
              <Icon name="building-2" size={15} color="var(--text-subtle)" />
              <span>{buyer}</span>
            </span>
            {tender.buyer_unit && (
              <>
                <span className="text-border-strong">·</span>
                <span>{tender.buyer_unit}</span>
              </>
            )}
            {tender.region && (
              <>
                <span className="text-border-strong">·</span>
                <span className="inline-flex items-center gap-1.5">
                  <Icon name="map-pin" size={15} color="var(--text-subtle)" />
                  <span>{tender.region}</span>
                </span>
              </>
            )}
          </div>
        </div>
      </header>

      {/* AI Compatibility Analysis CTA Card */}
      <QuotationEditor tenderId={tenderId} tenderCode={tender.code} tenderItems={tender.items} />
      <div className="mb-6 rounded-lg border border-primary/20 bg-gradient-to-b from-teal-50/40 to-white p-6 shadow-xs flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="flex size-10 items-center justify-center rounded-md bg-primary text-white shadow-sm">
            <Icon name="sparkles" size={20} />
          </span>
          <div>
            <h3 className="font-display text-lg font-bold text-text-strong mb-1">
              Análisis de compatibilidad IA
            </h3>
            <p className="text-sm text-text-muted mb-0">
              {cerrada
                ? "Esta licitación ya cerró: puedes revisar el análisis generado, pero no generar uno nuevo."
                : "Obtén una evaluación detallada de esta licitación según el perfil de tu empresa."}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            onClick={() => setIsAssistantOpen(true)}
            variant="ghost"
            className="shrink-0 border border-border-strong bg-white hover:bg-slate-50"
            id="btn-open-tender-assistant"
          >
            <span className="inline-flex items-center gap-2">
              <Icon name="message-square" size={16} />
              Consultar asistente virtual
            </span>
          </Button>


          {/* Una licitación cerrada no genera nada: si no hay análisis
              guardado, no hay a dónde ir. */}
          {(!cerrada || analysis) && (
            <Button
              onClick={() => router.push(`/matches/${tenderId}/analisis`)}
              variant="primary"
              className="shrink-0"
              id="btn-generate-ai-analysis"
            >
              <span className="inline-flex items-center gap-2">
                <Icon name="sparkles" size={16} />
                {cerrada || analysis
                  ? "Ver análisis de compatibilidad IA"
                  : "Generar análisis de compatibilidad IA"}
              </span>
            </Button>
          )}
        </div>
      </div>

      {/* El desfase se avisa, no se corrige solo: regenerar cuesta una llamada
          a la IA, así que la decisión es del usuario. */}
      {analysis?.is_outdated && !cerrada && (
        <div
          role="status"
          className="mb-6 flex flex-col gap-3 rounded-lg border border-warning/30 bg-warning-soft/40 p-4 sm:flex-row sm:items-center sm:justify-between"
        >
          <div className="flex items-start gap-3">
            <Icon name="triangle-alert" size={18} color="var(--amber-500)" />
            <div>
              <p className="text-sm font-semibold text-text-strong">
                Este análisis está desactualizado
              </p>
              <p className="mt-1 text-sm text-text-body mb-0">
                Tu perfil o la licitación cambiaron después de generarlo.
              </p>
            </div>
          </div>
          <Button
            variant="primary"
            onClick={handleRegenerateAnalysis}
            disabled={pendingAction !== null}
            className="shrink-0"
            id="btn-refresh-analysis"
          >
            {pendingAction === "analysis" ? (
              <span className="inline-flex items-center gap-2">
                <Icon name="loader-circle" className="animate-spin" size={16} />
                Actualizando…
              </span>
            ) : (
              <span className="inline-flex items-center gap-2">
                <Icon name="rotate-cw" size={16} />
                Actualizar análisis
              </span>
            )}
          </Button>
        </div>
      )}


      <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
        <KeyValueCard
          icon="wallet"
          eyebrow="Monto estimado"
          value={formatCLP(tender.available_amount_clp)}
        />
        <KeyValueCard
          icon="calendar"
          eyebrow="Cierre"
          value={formatClosingDate(tender.closing_at)}
          hint={closing.label}
        />
        <KeyValueCard
          icon="clock"
          eyebrow="Publicación"
          value={formatClosingDate(tender.published_at)}
        />
      </div>

      {/* Análisis de compatibilidad IA si ya existe */}
      {analysis && (
        <div className="mt-5 rounded-lg border border-primary-border bg-gradient-to-b from-teal-50/40 to-white p-6 shadow-xs">
          <div className="flex flex-col gap-5">
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <div className="flex items-center gap-3">
                <span className="flex size-9 items-center justify-center rounded-md bg-primary text-white shadow-sm">
                  <Icon name="sparkles" size={18} />
                </span>
                <div>
                  <h3 className="font-display text-lg font-bold text-text-strong mb-0.5">
                    Análisis de Compatibilidad IA
                  </h3>
                  <p className="text-xs text-text-muted mb-0">
                    Última actualización: {formatDateTime(analysis.updated_at)}
                  </p>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-6 border-t border-border-subtle pt-5 sm:grid-cols-4 items-center">
              <div className="flex flex-col items-center justify-center p-2">
                <MatchMeter
                  value={analysis.compatibility_score}
                  size="md"
                  thresholds={{ high: 70, mid: 40 }}
                  colors={{
                    high: "var(--green-500)",
                    mid: "var(--amber-500)",
                    low: "var(--red-500)",
                  }}
                />
                <div className="mt-2 text-[10px] font-bold uppercase tracking-caps text-text-subtle text-center">
                  Score de Compatibilidad
                </div>
              </div>

              <div className="sm:col-span-3 flex flex-col gap-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-semibold text-text-muted">Recomendación:</span>
                  <Badge
                    tone={
                      analysis.recommendation === "Postular"
                        ? "success"
                        : analysis.recommendation === "Evaluar con cautela"
                        ? "warning"
                        : "danger"
                    }
                    iconLeft={
                      <Icon
                        name={
                          analysis.recommendation === "Postular"
                            ? "circle-check"
                            : analysis.recommendation === "Evaluar con cautela"
                            ? "alert-triangle"
                            : "alert-circle"
                        }
                        size={12}
                      />
                    }
                  >
                    {analysis.recommendation}
                  </Badge>
                </div>
                <div className="text-sm leading-relaxed text-text-body whitespace-pre-line">
                  <h4 className="text-xs font-bold uppercase tracking-caps text-text-subtle mb-1">
                    Justificación del Análisis
                  </h4>
                  {analysis.justification}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      <Section title="Fechas importantes" icon="calendar">
        <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
          <DateRow label="Publicación" value={formatDateTime(tender.published_at)} />
          <DateRow label="Cierre" value={formatDateTime(tender.closing_at)} />
          <DateRow
            label="Última modificación"
            value={formatDateTime(tender.last_change_at)}
          />
        </dl>
      </Section>

      <Section title="Requisitos y descripción" icon="file-text">
        {tender.description ? (
          <p className="whitespace-pre-line text-sm leading-relaxed text-text-body">
            {tender.description}
          </p>
        ) : (
          <p className="text-sm italic text-text-subtle">
            El organismo no incluyó una descripción detallada.
          </p>
        )}

        {tender.items.length > 0 && (
          <div className="mt-5">
            <div className="mb-2 text-[10px] font-bold uppercase tracking-caps text-text-subtle">
              Ítems solicitados
            </div>
            <ul className="flex flex-col divide-y divide-border-subtle rounded-md border border-border-subtle">
              {tender.items.map((item) => (
                <li key={item.id} className="flex flex-col gap-1 p-3 sm:flex-row sm:items-start sm:gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-semibold text-text-strong">{item.name}</div>
                    {item.description && (
                      <div className="mt-0.5 text-xs text-text-muted">{item.description}</div>
                    )}
                  </div>
                  <div className="font-mono text-xs text-text-subtle">
                    {item.quantity} {item.unit_of_measure}
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </Section>

      <Section title="Documentos asociados" icon="paperclip">
        <p className="text-sm text-text-muted">
          Los documentos oficiales (bases, anexos y aclaraciones) están disponibles
          directamente en Mercado Público.
        </p>
        <a
          href={officialUrl}
          target="_blank"
          rel="noreferrer noopener"
          className="mt-3 inline-flex items-center gap-2 rounded-md bg-primary-soft px-4 py-2 text-sm font-bold text-primary hover:bg-teal-100 transition-colors"
        >
          Ver documentos en Mercado Público
          <Icon name="external-link" size={14} />
        </a>
      </Section>

      <Section title="Enlaces relacionados" icon="link">
        <ul className="flex flex-col gap-2 text-sm">
          <li>
            <a
              href={officialUrl}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-1.5 font-semibold text-text-link hover:underline"
            >
              Ficha oficial en Mercado Público
              <Icon name="external-link" size={13} />
            </a>
          </li>
          <li className="text-text-muted">
            Código de licitación: <span className="font-mono text-text-strong">{tender.code}</span>
          </li>
          <li className="text-text-muted">
            RUT comprador: <span className="font-mono text-text-strong">{tender.buyer_rut}</span>
          </li>
        </ul>
      </Section>

      <TenderAssistantDrawer
        tenderId={tenderId}
        tenderTitle={tender.name}
        isOpen={isAssistantOpen}
        onClose={() => setIsAssistantOpen(false)}
      />
    </section>
  );

}

function Section({
  title,
  icon,
  children,
}: {
  title: string;
  icon: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mt-5 rounded-lg border border-border-subtle bg-surface-card p-6 shadow-xs">
      <div className="mb-3 inline-flex items-center gap-2 text-sm font-bold text-text-strong">
        <Icon name={icon} size={16} color="var(--primary)" />
        {title}
      </div>
      {children}
    </div>
  );
}

function KeyValueCard({
  icon,
  eyebrow,
  value,
  hint,
}: {
  icon: string;
  eyebrow: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="rounded-lg border border-border-subtle bg-surface-card p-4 shadow-xs">
      <div className="mb-1 inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-caps text-text-subtle">
        <Icon name={icon} size={12} color="var(--text-subtle)" />
        {eyebrow}
      </div>
      <div className="font-mono text-lg font-semibold text-text-strong">{value}</div>
      {hint && <div className="mt-0.5 text-xs text-text-muted">{hint}</div>}
    </div>
  );
}

function DateRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-[10px] font-bold uppercase tracking-caps text-text-subtle">{label}</dt>
      <dd className="font-mono text-sm text-text-strong">{value}</dd>
    </div>
  );
}
