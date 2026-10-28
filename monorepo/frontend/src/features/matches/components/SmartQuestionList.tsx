"use client";

import React, { useEffect, useState } from "react";
import { Sparkles, CheckCircle2, AlertCircle, RefreshCw } from "lucide-react";
import type { DynamicQuestionDTO } from "../questionTypes";
import { getSmartQuestions } from "../services/questionService";
import { SmartQuestionCard } from "./SmartQuestionCard";

export interface SmartQuestionListProps {
  tenderId: string;
  className?: string;
  onAllAnswered?: () => void;
}

export function SmartQuestionList({
  tenderId,
  className = "",
  onAllAnswered,
}: SmartQuestionListProps) {
  const [questions, setQuestions] = useState<DynamicQuestionDTO[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchQuestions = React.useCallback(async () => {
    if (!tenderId) return;

    setIsLoading(true);
    setError(null);

    try {
      // Invocación a GET /questions?tender_id={id}
      const data = await getSmartQuestions(tenderId);
      setQuestions(data);
    } catch (err) {
      const errorMsg =
        err instanceof Error
          ? err.message
          : "Error al cargar las preguntas inteligentes de la licitación.";
      setError(errorMsg);
    } finally {
      setIsLoading(false);
    }
  }, [tenderId]);

  useEffect(() => {
    void fetchQuestions();
  }, [fetchQuestions]);

  const handleAnswered = (id: string) => {
    setQuestions((prev) => {
      const remaining = prev.filter((q) => q.id !== id);
      if (remaining.length === 0 && onAllAnswered) {
        onAllAnswered();
      }
      return remaining;
    });
  };

  // 1. Estado de carga: Skeletons animados con acento IA
  if (isLoading) {
    return (
      <div className={`space-y-4 ${className}`}>
        <div className="flex items-center gap-2 text-xs font-medium text-teal-700 dark:text-teal-400">
          <Sparkles className="size-4 animate-spin text-teal-600 dark:text-teal-400" />
          <span>Analizando bases y perfil para generar preguntas inteligentes...</span>
        </div>
        {[1, 2].map((n) => (
          <div
            key={n}
            className="animate-pulse rounded-2xl border border-warm-200 bg-white p-6 dark:border-warm-800 dark:bg-warm-900/60"
          >
            <div className="h-4 w-28 rounded-full bg-warm-200 dark:bg-warm-800" />
            <div className="mt-4 h-5 w-3/4 rounded bg-warm-200 dark:bg-warm-800" />
            <div className="mt-2 h-3.5 w-1/2 rounded bg-warm-100 dark:bg-warm-800/60" />
            <div className="mt-6 flex justify-end gap-3">
              <div className="h-9 w-28 rounded-lg bg-warm-100 dark:bg-warm-800" />
              <div className="h-9 w-28 rounded-lg bg-teal-100 dark:bg-teal-950" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  // 2. Estado de error con reintento
  if (error) {
    return (
      <div
        role="alert"
        className={`flex items-center justify-between rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-300 ${className}`}
      >
        <div className="flex items-center gap-2">
          <AlertCircle className="size-5 shrink-0 text-red-600 dark:text-red-400" />
          <span>{error}</span>
        </div>
        <button
          type="button"
          onClick={() => void fetchQuestions()}
          className="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold hover:bg-red-100 dark:hover:bg-red-900/40"
        >
          <RefreshCw className="size-3.5" />
          <span>Reintentar</span>
        </button>
      </div>
    );
  }

  // 3. Sin preguntas pendientes
  if (questions.length === 0) {
    return null;
  }

  // 4. Lista interactiva de tarjetas
  return (
    <section aria-label="Preguntas Estratégicas de la Licitación" className={`space-y-4 ${className}`}>
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-text-strong dark:text-warm-100">
          <Sparkles className="size-4 text-teal-600 dark:text-teal-400" />
          <span>Preguntas Estratégicas Recomendadas</span>
        </h2>
        <span className="rounded-full bg-teal-100 px-2 py-0.5 text-xs font-semibold text-teal-800 dark:bg-teal-950 dark:text-teal-300">
          {questions.length} {questions.length === 1 ? "pendiente" : "pendientes"}
        </span>
      </div>

      <div className="flex flex-col gap-4">
        {questions.map((question) => (
          <div
            key={question.id}
            className="transition-all duration-300 animate-in fade-in slide-in-from-top-2"
          >
            <SmartQuestionCard
              question={question}
              onAnswered={handleAnswered}
            />
          </div>
        ))}
      </div>
    </section>
  );
}
