"use client";

import { useState } from "react";
import { Button } from "@/features/shared/components/Button";
import type { Question } from "../questionTypes";

interface Props {
  question: Question;
  onSubmit: (answer: string) => void;
  onOmit: () => void;
}

export function SmartQuestionCard({ question, onSubmit, onOmit }: Props) {
  const [answer, setAnswer] = useState("");

  const hasAnswer = answer.trim().length > 0;
  const isChoiceQuestion = question.options.length > 0;

  function handleSubmit() {
    if (!hasAnswer) return;
    onSubmit(answer.trim());
  }

  return (
    <div className="mx-auto w-full max-w-3xl rounded-xl border border-border-subtle bg-surface-card p-6 shadow-sm">
      <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-text-subtle">
        Pregunta
      </p>
      <p className="mb-5 text-base font-semibold text-text-strong">{question.question}</p>

      {isChoiceQuestion ? (
        <fieldset className="flex flex-col gap-2.5">
          <legend className="sr-only">Selecciona una opción</legend>
          {question.options.map((opt) => (
            <label
              key={opt}
              className="flex cursor-pointer items-center gap-3 rounded-lg border border-border-subtle bg-white px-4 py-3 text-sm text-text-body transition-colors hover:border-primary hover:bg-primary-soft has-[:checked]:border-primary has-[:checked]:bg-primary-soft"
            >
              <input
                type="radio"
                name={`q-${question.id}`}
                value={opt}
                checked={answer === opt}
                onChange={() => setAnswer(opt)}
                className="accent-primary"
              />
              {opt}
            </label>
          ))}
        </fieldset>
      ) : (
        <textarea
          aria-label={question.question}
          rows={3}
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          placeholder="Escribe tu respuesta…"
          className="w-full rounded-md border border-border-default bg-white px-3.5 py-2.5 text-sm text-text-body placeholder:text-text-subtle transition-all duration-200 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 hover:border-border-strong resize-none"
        />
      )}

      <div className="mt-5 flex items-center justify-end gap-3">
        <Button variant="ghost" onClick={onOmit}>
          Omitir
        </Button>
        <Button variant="primary" onClick={handleSubmit} disabled={!hasAnswer}>
          Enviar
        </Button>
      </div>
    </div>
  );
}
