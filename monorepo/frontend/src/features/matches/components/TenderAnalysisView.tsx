"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/features/auth/AuthContext";
import { ApiError, TimeoutError } from "@/features/shared/api/client";
import { Badge } from "@/features/shared/components/Badge";
import { Button } from "@/features/shared/components/Button";
import { Icon } from "@/features/shared/components/Icon";
import { MatchMeter } from "@/features/shared/components/MatchMeter";
import { Textarea } from "@/features/shared/components/Textarea";
import { getRecommendedTenders, getDeepAnalysis, generateDeepAnalysis } from "../services/tenderService";
import type { MatchingResult, Tender, DeepAnalysis } from "../tenderTypes";
import { formatDateTime, normalizeScore } from "../utils/format";

interface TenderAnalysisViewProps {
  tenderId: string;
}

type LoadState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ready"; match: MatchingResult }
  | { kind: "not-found" }
  | { kind: "error"; message: string };

const ANALYSIS_THRESHOLDS = { high: 70, mid: 40 };
const ANALYSIS_COLORS = {
  high: "var(--green-500)",
  mid: "var(--amber-500)",
  low: "var(--red-500)",
};

export function TenderAnalysisView({ tenderId }: TenderAnalysisViewProps) {
  const router = useRouter();
  const { user, isLoading: authLoading, isAuthenticated } = useAuth();
  const [state, setState] = useState<LoadState>({ kind: "idle" });
  const [analysis, setAnalysis] = useState<DeepAnalysis | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(true);
  const [regenerating, setRegenerating] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [promptError, setPromptError] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [retryNonce, setRetryNonce] = useState(0);

  // 1. Cargar información de la licitación (match)
  useEffect(() => {
    if (authLoading) return;
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }
    if (!user) return;

    let cancelled = false;
    setState({ kind: "loading" });
    void (async () => {
      try {
        const matches = await getRecommendedTenders(user.id);
        if (cancelled) return;
        const found = matches.find((m) => m.tender?.id === tenderId);
        if (!found) {
          setState({ kind: "not-found" });
          return;
        }
        setState({ kind: "ready", match: found });
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError || err instanceof TimeoutError) {
          setState({ kind: "error", message: err.message });
          return;
        }
        setState({
          kind: "error",
          message: "No pudimos cargar la información de la licitación.",
        });
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [authLoading, isAuthenticated, user, router, tenderId, retryNonce]);

  // 2. Cargar u obtener el análisis profundo inicial
  useEffect(() => {
    if (state.kind !== "ready") return;

    let cancelled = false;
    setAnalysisLoading(true);
    setErrorMsg("");

    getDeepAnalysis(tenderId)
      .then((res) => {
        if (cancelled) return;
        setAnalysis(res);
        setAnalysisLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        // Si no existe, o hay otro tipo de error, se maneja aquí
        setAnalysis(null);
        setErrorMsg(err instanceof Error ? err.message : "Error al obtener el análisis de compatibilidad.");
        setAnalysisLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [tenderId, state.kind, retryNonce]);

  // 3. Manejar el flujo de regeneración manual del análisis con prompt
  const handleRegenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (prompt.length > 1000) {
      setPromptError("El prompt no puede superar los 1000 caracteres.");
      return;
    }

    setRegenerating(true);
    setErrorMsg("");
    setPromptError("");

    try {
      const res = await generateDeepAnalysis(tenderId, prompt, true);
      setAnalysis(res);
      setPrompt("");
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Error al regenerar el análisis.");
    } finally {
      setRegenerating(false);
    }
  };

  if (authLoading || state.kind === "idle" || state.kind === "loading") {
    return (
      <section className="mx-auto w-full max-w-4xl">
        <BackLink tenderId={tenderId} />
        <div className="rounded-lg border border-border-subtle bg-surface-card p-10 text-center text-sm text-text-muted">
          Cargando análisis de compatibilidad…
        </div>
      </section>
    );
  }

  if (state.kind === "not-found") {
    return (
      <section className="mx-auto w-full max-w-4xl">
        <BackLink tenderId={tenderId} />
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
        <BackLink tenderId={tenderId} />
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
  const score = normalizeScore(match.final_score);
  const buyer = tender.buyer_name ?? "Organismo no especificado";

  return (
    <section className="mx-auto w-full max-w-4xl">
      <BackLink tenderId={tenderId} />

      <header className="mb-6 flex flex-col gap-4 rounded-lg border border-border-subtle bg-surface-card p-6 shadow-xs">
        <div className="flex items-center gap-2">
          <Badge tone="teal">Compra Ágil</Badge>
          <span className="font-mono text-xs text-text-subtle">ID {tender.code}</span>
        </div>
        <h1 className="font-display text-2xl font-bold leading-tight text-text-strong">
          Análisis de compatibilidad IA: {tender.name}
        </h1>
        <p className="text-sm text-text-muted mb-0">
          Entidad compradora: <span className="font-semibold text-text-strong">{buyer}</span>
        </p>
      </header>

      {analysisLoading ? (
        <div className="rounded-lg border border-border-subtle bg-surface-card p-10 text-center text-sm text-text-muted">
          <div className="flex items-center justify-center py-6 text-sm text-text-muted gap-2">
            <Icon name="loader-2" className="animate-spin text-primary" size={18} />
            Evaluando requerimientos de la licitación y perfil del proveedor…
          </div>
        </div>
      ) : analysis ? (
        <div className="flex flex-col gap-6">
          {/* Tarjeta Principal de Análisis */}
          <div className="rounded-lg border border-primary-border bg-gradient-to-b from-teal-50/40 to-white p-6 shadow-xs">
            <div className="flex flex-col gap-5">
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div className="flex items-center gap-3">
                  <span className="flex size-9 items-center justify-center rounded-md bg-primary text-white shadow-sm">
                    <Icon name="sparkles" size={18} />
                  </span>
                  <div>
                    <h3 className="font-display text-lg font-bold text-text-strong mb-0.5">
                      Evaluación de Compatibilidad
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
                    thresholds={ANALYSIS_THRESHOLDS}
                    colors={ANALYSIS_COLORS}
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
                    <h4 className="text-xs font-bold uppercase tracking-caps text-text-subtle mb-1">Justificación del Análisis</h4>
                    {analysis.justification}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Formulario de Regeneración Personalizada */}
          <div className="rounded-lg border border-border-subtle bg-surface-card p-6 shadow-xs">
            <h3 className="font-display text-lg font-bold text-text-strong mb-2 flex items-center gap-2">
              <Icon name="sliders" size={18} className="text-primary" />
              Regenerar Análisis con Enfoque Personalizado
            </h3>
            <p className="text-sm text-text-muted mb-4">
              Si quieres que la IA priorice algún aspecto (ej. certificaciones específicas, plazos de entrega, o experiencia regional), escribe tus instrucciones a continuación.
            </p>

            <form onSubmit={handleRegenerate} className="flex flex-col gap-4">
              <Textarea
                label="Instrucciones del prompt (opcional)"
                value={prompt}
                onChange={(e) => {
                  setPrompt(e.target.value);
                  if (e.target.value.length > 1000) {
                    setPromptError("Las instrucciones no pueden superar los 1000 caracteres.");
                  } else {
                    setPromptError("");
                  }
                }}
                charCount={prompt.length}
                maxChars={1000}
                error={promptError}
                placeholder="Ej: Dar mayor importancia a la experiencia en el sector público de salud y a la certificación ISO 14001."
                id="prompt-input"
              />
              
              {errorMsg && (
                <div className="rounded-md bg-danger-soft/30 border border-danger/20 p-3 text-sm text-danger font-medium">
                  {errorMsg}
                </div>
              )}

              <Button
                type="submit"
                variant="primary"
                disabled={regenerating || !!promptError}
                className="self-end"
                id="btn-regenerate-analysis"
              >
                {regenerating ? (
                  <span className="inline-flex items-center gap-2">
                    <Icon name="loader-2" className="animate-spin" size={16} />
                    Regenerando análisis…
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-2">
                    <Icon name="rotate-cw" size={16} />
                    Regenerar análisis
                  </span>
                )}
              </Button>
            </form>
          </div>
        </div>
      ) : (
        <div className="rounded-lg border border-border-subtle bg-surface-card p-6 text-center text-sm text-text-muted">
          <p>No se pudo generar el análisis. Inténtalo de nuevo.</p>
          <Button
            variant="primary"
            onClick={() => setRetryNonce((n) => n + 1)}
            className="mt-2"
          >
            Reintentar generación
          </Button>
        </div>
      )}
    </section>
  );
}

function BackLink({ tenderId }: { tenderId: string }) {
  return (
    <Link
      href={`/matches/${tenderId}`}
      className="mb-4 inline-flex items-center gap-1.5 text-sm font-semibold text-text-muted hover:text-primary transition-colors"
      id="lnk-back-to-tender"
    >
      <Icon name="arrow-left" size={14} />
      Volver al detalle de la licitación
    </Link>
  );
}
