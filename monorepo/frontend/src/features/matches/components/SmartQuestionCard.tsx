"use client";

import React, { useState } from "react";
import { Sparkles, Check, X, Loader2, CheckCircle2, AlertCircle } from "lucide-react";
import type { DynamicQuestionDTO } from "../questionTypes";
import { answerSmartQuestion } from "../services/questionService";

export interface SmartQuestionCardProps {
  question: DynamicQuestionDTO;
  onAnswered?: (id: string) => void;
  className?: string;
  // Compatibilidad con invocaciones previas
  onSubmit?: (answer: string) => void;
  onOmit?: () => void;
}

export function SmartQuestionCard({
  question,
  onAnswered,
  className = "",
  onSubmit,
  onOmit,
}: SmartQuestionCardProps) {
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [isSuccess, setIsSuccess] = useState<boolean>(false);
  const [submittingAction, setSubmittingAction] = useState<"Sí" | "No" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleAnswer(choice: "Sí" | "No") {
    if (isSubmitting || isSuccess) return;

    setIsSubmitting(true);
    setSubmittingAction(choice);
    setError(null);

    try {
      // 1. Ejecutar el POST al backend con el nuevo formato de payload
      await answerSmartQuestion({
        question_id: question.id,
        answer: choice,
      });

      // 2. Feedback visual exitoso
      setIsSuccess(true);

      // Si existe un handler legacy onSubmit, también lo notificamos
      if (onSubmit) {
        onSubmit(choice);
      }

      // 3. Esperar un breve instante para que el usuario aprecie el check verde antes de remover la tarjeta
      setTimeout(() => {
        onAnswered?.(question.id);
      }, 700);
    } catch (err) {
      const errorMessage =
        err instanceof Error
          ? err.message
          : "No pudimos registrar tu respuesta. Inténtalo de nuevo.";
      setError(errorMessage);
      setIsSubmitting(false);
      setSubmittingAction(null);
    }
  }

  return (
    <div
      className={`relative overflow-hidden rounded-2xl border border-teal-500/30 bg-surface-card p-5 sm:p-6 shadow-xs transition-all duration-300 hover:border-teal-500/50 hover:shadow-md dark:border-teal-400/20 dark:bg-warm-900/90 dark:hover:border-teal-400/40 ${
        isSuccess
          ? "border-green-500/50 bg-green-50/20 dark:border-green-500/40 dark:bg-green-950/20"
          : ""
      } ${className}`}
    >
      {/* Indicador de acento superior estilo IA */}
      <div
        className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-teal-400 via-teal-600 to-amber-400 opacity-80"
        aria-hidden
      />

      {/* Encabezado con insignia IA y keyword objetivo */}
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="inline-flex items-center gap-1.5 rounded-full border border-teal-200/90 bg-teal-50 px-2.5 py-0.5 text-xs font-semibold text-teal-800 dark:border-teal-800/70 dark:bg-teal-950/80 dark:text-teal-300">
          <Sparkles className="size-3.5 text-teal-600 dark:text-teal-400" />
          <span>Pregunta Inteligente</span>
        </div>

        {question.target_keyword && (
          <span className="text-xs text-text-subtle dark:text-warm-400">
            Ajusta:{" "}
            <code className="rounded bg-warm-100 px-1.5 py-0.5 font-mono text-[11px] font-medium text-text-strong dark:bg-warm-800 dark:text-warm-200">
              {question.target_keyword}
            </code>
          </span>
        )}
      </div>

      {/* Texto de la pregunta */}
      <h3 className="mb-2 text-base font-semibold leading-snug text-text-strong sm:text-lg dark:text-warm-100">
        {question.question}
      </h3>

      <p className="mb-5 text-xs text-text-muted sm:text-sm dark:text-warm-400">
        Responder afirmativamente indexa esta capacidad en tu perfil para mejorar tus matches de Mercado Público.
      </p>

      {/* Mensaje de error si falla la llamada */}
      {error && (
        <div
          role="alert"
          className="mb-4 flex items-center justify-between gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-300 sm:text-sm"
        >
          <div className="flex items-center gap-2">
            <AlertCircle className="size-4 shrink-0 text-red-600 dark:text-red-400" />
            <span>{error}</span>
          </div>
          <button
            type="button"
            onClick={() => setError(null)}
            className="text-xs font-medium underline hover:no-underline"
          >
            Reintentar
          </button>
        </div>
      )}

      {/* Estado de Éxito / Feedback */}
      {isSuccess ? (
        <div className="flex items-center gap-2.5 rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-green-800 transition-all dark:border-green-800/60 dark:bg-green-950/50 dark:text-green-300">
          <CheckCircle2 className="size-5 shrink-0 text-green-600 dark:text-green-400" />
          <div className="text-sm">
            <p className="font-semibold">¡Respuesta registrada con éxito!</p>
            <p className="text-xs text-green-700 dark:text-green-400">
              Refinando recomendaciones de licitaciones...
            </p>
          </div>
        </div>
      ) : (
        /* Acciones: Dos botones con estado de carga */
        <div className="mt-4 flex flex-wrap items-center justify-end gap-3">
          <button
            type="button"
            onClick={() => {
              if (onOmit) {
                onOmit();
              } else {
                handleAnswer("No");
              }
            }}
            disabled={isSubmitting || isSuccess}
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-border-default bg-transparent px-4 py-2 text-sm font-medium text-text-muted transition-all duration-200 hover:bg-warm-100 hover:text-text-strong disabled:cursor-not-allowed disabled:opacity-50 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-warm-400 dark:border-warm-700 dark:text-warm-300 dark:hover:bg-warm-800 dark:hover:text-warm-100"
          >
            {isSubmitting && submittingAction === "No" ? (
              <Loader2 className="size-4 animate-spin text-text-muted dark:text-warm-300" />
            ) : (
              <X className="size-4 text-text-muted dark:text-warm-400" />
            )}
            <span>No, descartar</span>
          </button>

          <button
            type="button"
            onClick={() => handleAnswer("Sí")}
            disabled={isSubmitting || isSuccess}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-on-primary shadow-teal transition-all duration-200 hover:bg-primary-hover active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 dark:bg-teal-600 dark:hover:bg-teal-500"
          >
            {isSubmitting && submittingAction === "Sí" ? (
              <Loader2 className="size-4 animate-spin text-white" />
            ) : (
              <Check className="size-4 text-white" />
            )}
            <span>Sí, lo tengo</span>
          </button>
        </div>
      )}
    </div>
  );
}
