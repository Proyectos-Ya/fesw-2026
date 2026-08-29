"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/features/auth/AuthContext";
import { ApiError, TimeoutError } from "@/features/shared/api/client";
import { Button } from "@/features/shared/components/Button";
import { Icon } from "@/features/shared/components/Icon";
import { getRecommendedTenders } from "../services/tenderService";
import type { MatchingResult } from "../tenderTypes";
import type { Question } from "../questionTypes";
import { normalizeScore } from "../utils/format";
import { useSmartQuestions } from "../hooks/useSmartQuestions";
import { SmartQuestionsBanner } from "./SmartQuestionsBanner";
import { SmartQuestionCard } from "./SmartQuestionCard";
import { TenderCard } from "./TenderCard";
import { TenderCardSkeleton } from "./TenderCardSkeleton";
import { answerSmartQuestion } from "../services/questionService";

const GREEN_THRESHOLD = 70;

type LoadState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ready"; matches: MatchingResult[] }
  | { kind: "no-supplier" }
  | { kind: "error"; message: string };

export function HomeDashboard() {
  const router = useRouter();
  const { user, isLoading: authLoading, isAuthenticated } = useAuth();
  const [state, setState] = useState<LoadState>({ kind: "idle" });
  const [retryNonce, setRetryNonce] = useState(0);

  const { questions: fetchedQuestions } = useSmartQuestions(user?.id ?? "");
  const [pendingQuestions, setPendingQuestions] = useState<Question[]>([]);
  const [showCard, setShowCard] = useState(false);
  const [isAnswering, setIsAnswering] = useState(false);

  useEffect(() => {
    setPendingQuestions(fetchedQuestions);
  }, [fetchedQuestions]);

  function handleBannerOpen() {
    if (pendingQuestions.length > 0) setShowCard(true);
  }

async function handleAnswer(questionId: string, targetField: string, answerValue: string) {
    if (!user?.id || isAnswering) return;

    setIsAnswering(true);
    try {
      await answerSmartQuestion({
        supplier_id: user?.id,
        question_id: questionId,
        target_profile_field: targetField,
        answer: answerValue,
      });
      
      advanceQueue();

      setRetryNonce((n) => n + 1);

    } catch (error) {
      console.error("Error al responder la pregunta:", error);
    } finally {
      setIsAnswering(false);
    }
  }

  function advanceQueue() {
    setPendingQuestions((prev) => {
      const next = prev.slice(1);
      if (next.length === 0) setShowCard(false);
      return next;
    });
  }

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
        const all = await getRecommendedTenders(user.id);
        if (cancelled) return;
        const green = all.filter((m) => normalizeScore(m.final_score) >= GREEN_THRESHOLD);
        setState({ kind: "ready", matches: green });
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) {
          setState({ kind: "no-supplier" });
          return;
        }
        if (err instanceof ApiError || err instanceof TimeoutError) {
          setState({ kind: "error", message: err.message });
          return;
        }
        setState({ kind: "error", message: "No pudimos cargar tus recomendaciones." });
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [authLoading, isAuthenticated, user, router, retryNonce]);

  if (authLoading || state.kind === "idle" || state.kind === "loading") {
    return (
      <section className="mx-auto w-full max-w-3xl">
        <PageHeader />
        <div className="flex flex-col gap-4">
          <TenderCardSkeleton />
          <TenderCardSkeleton />
          <TenderCardSkeleton />
        </div>
      </section>
    );
  }

  if (state.kind === "no-supplier") {
    return (
      <section className="mx-auto w-full max-w-3xl">
        <PageHeader />
        <div className="rounded-lg border border-border-subtle bg-surface-card p-10 text-center shadow-xs">
          <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-full bg-primary-soft">
            <Icon name="sparkles" size={22} color="var(--primary)" />
          </div>
          <h2 className="font-display text-2xl font-bold text-text-strong">
            Primero crea tu perfil inteligente
          </h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-text-muted">
            Necesitamos saber el rubro, regiones y experiencia de tu empresa para mostrarte
            licitaciones que realmente calcen.
          </p>
          <Link
            href="/perfil"
            className="mt-6 inline-flex items-center gap-2 rounded-full bg-primary px-6 py-3 text-sm font-bold text-on-primary shadow-teal hover:bg-primary-hover transition-colors"
          >
            Construir mi perfil
            <Icon name="arrow-right" size={16} />
          </Link>
        </div>
      </section>
    );
  }

  if (state.kind === "error") {
    return (
      <section className="mx-auto w-full max-w-3xl">
        <PageHeader />
        <div className="rounded-lg border border-danger/20 bg-danger-soft/30 p-6 text-center">
          <p className="text-sm font-medium text-danger">{state.message}</p>
          <Button variant="primary" className="mt-4" onClick={() => setRetryNonce((n) => n + 1)}>
            Reintentar
          </Button>
        </div>
      </section>
    );
  }

  const { matches } = state;

  return (
    <section className="mx-auto w-full max-w-3xl">
      <PageHeader />
      <SmartQuestionsBanner questions={pendingQuestions} onOpen={handleBannerOpen} />
      {showCard && pendingQuestions[0] && (
        <div className="mb-6">
          <SmartQuestionCard
            key={pendingQuestions[0].id}
            question={pendingQuestions[0]}
            onSubmit={(value: string) => 
              handleAnswer(
                pendingQuestions[0].id, 
                pendingQuestions[0].target_profile_field, 
                value
              )
            }
            onOmit={() => advanceQueue()}
          />
        </div>
      )}
      {matches.length === 0 ? (
        <EmptyGreen />
      ) : (
        <>
          <div className="flex flex-col gap-4">
            {matches.map((m) => (
              <TenderCard key={m.id} match={m} />
            ))}
          </div>
          <div className="mt-6 text-center">
            <Link
              href="/matches"
              className="inline-flex items-center gap-2 rounded-full border border-border-default bg-white px-6 py-3 text-sm font-bold text-text-strong shadow-xs hover:border-primary hover:text-primary transition-colors"
            >
              Ver todos los matches
              <Icon name="arrow-right" size={16} />
            </Link>
          </div>
        </>
      )}
    </section>
  );
}

function PageHeader() {
  return (
    <div className="mb-6">
      <div className="eyebrow mb-2">Inicio</div>
      <h1 className="font-display text-3xl font-bold tracking-tight text-text-strong sm:text-4xl">
        Tus mejores licitaciones de hoy
      </h1>
      <p className="mt-2 text-base text-text-muted">
        Licitaciones con alta compatibilidad con el perfil de tu empresa.
      </p>
    </div>
  );
}

function EmptyGreen() {
  return (
    <div className="rounded-lg border border-border-subtle bg-surface-card p-10 text-center shadow-xs">
      <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-full bg-warm-100">
        <Icon name="search" size={22} color="var(--text-subtle)" />
      </div>
      <h2 className="font-display text-xl font-semibold text-text-strong">
        Sin licitaciones de alta compatibilidad hoy
      </h2>
      <p className="mx-auto mt-2 max-w-md text-sm text-text-muted">
        No hay matches con puntuación alta por ahora. Puedes revisar todos tus matches para ver
        opciones con compatibilidad media o baja.
      </p>
      <Link
        href="/matches"
        className="mt-6 inline-flex items-center gap-2 rounded-full border border-border-default bg-white px-6 py-3 text-sm font-bold text-text-strong shadow-xs hover:border-primary hover:text-primary transition-colors"
      >
        Ver todos los matches
        <Icon name="arrow-right" size={16} />
      </Link>
    </div>
  );
}
