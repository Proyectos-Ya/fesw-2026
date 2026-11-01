"use client";

import React, { useState } from "react";
import { Sparkles, Check, X, Loader2, CheckCircle2, AlertCircle } from "lucide-react";
import { Badge } from "@/features/shared/components/Badge";
import { Button } from "@/features/shared/components/Button";
import type { DynamicQuestionDTO, Question } from "../questionTypes";
import { answerSmartQuestion } from "../services/questionService";

export interface SmartQuestionCardProps {
  question: DynamicQuestionDTO | Question;
  progress?: { current: number; total: number };
  onAnswered?: (id: string) => void;
  className?: string;
  // Compatibilidad con invocaciones previas
  onSubmit?: (answer: string) => void;
  onOmit?: () => void;
}

export function SmartQuestionCard({
  question,
  progress,
  onAnswered,
  className = "",
  onSubmit,
  onOmit,
}: SmartQuestionCardProps) {
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [isSuccess, setIsSuccess] = useState<boolean>(false);
  const [isFadingOut, setIsFadingOut] = useState<boolean>(false);
  const [submittingAction, setSubmittingAction] = useState<"Sí" | "No" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleAnswer(choice: "Sí" | "No") {
    if (isSubmitting || isSuccess) return;

    setIsSubmitting(true);
    setSubmittingAction(choice);
    setError(null);

    try {
      // 1. Ejecutar el POST al backend con el formato de payload
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

      // 3. Pequeña pausa para apreciar el check verde, luego fade-out antes de avanzar
      setTimeout(() => {
        setIsFadingOut(true);
        setTimeout(() => {
          onAnswered?.(question.id);
        }, 150);
      }, 250);
    } catch (err) {
      const errorMessage =
        err instanceof Error
          ? err.message
          : "No pudimos registrar tu respuesta. Inténtalo de nuevo.";
      setError(errorMessage);
      setIsSubmitting(false);
      setSubmittingAction(null);
      setIsFadingOut(false);
    }
  }

  return (
    <div
      className={`relative overflow-hidden rounded-lg border border-border-subtle bg-surface-card p-6 shadow-xs transition-all duration-200 hover:shadow-sm ${
        isSuccess ? "border-success/30 bg-success-soft/40" : ""
      } ${className}`}
    >
      <div
        className={`transition-opacity duration-150 ease-out ${
          isFadingOut ? "opacity-0" : "opacity-100"
        }`}
      >
        {/* Encabezado con insignia IA y requisito objetivo */}
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <Badge tone="teal" iconLeft={<Sparkles className="size-3.5 text-primary" />}>
            Pregunta Inteligente
          </Badge>

          {question.target_keyword && (
            <span className="inline-flex items-center rounded-md bg-surface-inset px-2 py-0.5 text-xs font-medium text-text-subtle">
              <span className="sr-only">Requisito detectado: </span>
              {question.target_keyword}
            </span>
          )}
        </div>

        {/* Texto de la pregunta */}
        <h3 className="mb-2 font-display text-lg font-semibold leading-snug text-text-strong">
          {question.question}
        </h3>

        <p className="mb-6 text-sm leading-relaxed text-text-muted">
          Si tu empresa cuenta con esta capacidad técnica o certificación, responder afirmativamente la incorporará a tu perfil para mejorar tu compatibilidad con licitaciones afines.
        </p>

        {/* Mensaje de error si falla la llamada */}
        {error && (
          <div
            role="alert"
            className="mb-4 flex items-center justify-between gap-2 rounded-lg border border-danger/20 bg-danger-soft/30 p-3 text-xs text-danger sm:text-sm"
          >
            <div className="flex items-center gap-2">
              <AlertCircle className="size-4 shrink-0 text-danger" />
              <span>{error}</span>
            </div>
            <button
              type="button"
              onClick={() => setError(null)}
              className="text-xs font-semibold underline hover:no-underline"
            >
              Reintentar
            </button>
          </div>
        )}

        {/* Estado de Éxito / Feedback */}
        {isSuccess ? (
          <div className="flex items-center justify-between rounded-lg border border-success/30 bg-success-soft px-4 py-3 text-success-text">
            <div className="flex items-center gap-3">
              <CheckCircle2 className="size-5 shrink-0 text-success" />
              <div className="text-sm">
                <p className="font-semibold">¡Respuesta registrada con éxito!</p>
                <p className="text-xs text-success-text">
                  Refinando recomendaciones de licitaciones...
                </p>
              </div>
            </div>
            {progress && (
              <span className="font-mono text-xs font-semibold text-success-text">
                {progress.current}/{progress.total}
              </span>
            )}
          </div>
        ) : (
          /* Acciones y Progreso: Contador abajo a la izquierda y botones a la derecha */
          <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
            <div>
              {progress && (
                <span
                  data-testid="question-progress"
                  className="font-mono text-xs font-semibold text-text-subtle"
                >
                  {progress.current}/{progress.total}
                </span>
              )}
            </div>

            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => {
                  if (onOmit && !onAnswered) {
                    onOmit();
                  } else {
                    handleAnswer("No");
                  }
                }}
                disabled={isSubmitting || isSuccess}
                className="inline-flex items-center justify-center gap-2 rounded-md border border-border-default bg-surface-card px-4 py-2 text-sm font-semibold text-text-default transition-all duration-200 hover:bg-surface-hover hover:text-text-strong disabled:cursor-not-allowed disabled:opacity-50 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
              >
                {isSubmitting && submittingAction === "No" ? (
                  <Loader2 className="size-4 animate-spin text-text-muted" />
                ) : (
                  <X className="size-4 text-text-muted" />
                )}
                <span>No, descartar</span>
              </button>

              <Button
                variant="primary"
                onClick={() => handleAnswer("Sí")}
                disabled={isSubmitting || isSuccess}
                isLoading={isSubmitting && submittingAction === "Sí"}
              >
                {!isSubmitting && <Check className="size-4" />}
                <span>Sí, lo tengo</span>
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
