"use client";

import { Icon } from "@/features/shared/components/Icon";
import { Button } from "@/features/shared/components/Button";
import type { Question } from "../questionTypes";

interface Props {
  questions: Question[];
  onOpen: () => void;
}

export function SmartQuestionsBanner({ questions, onOpen }: Props) {
  if (questions.length === 0) return null;

  const count = questions.length;
  const label =
    count === 1
      ? "Tienes 1 pregunta pendiente para mejorar tus matches"
      : `Tienes ${count} preguntas pendientes para mejorar tus matches`;

  return (
    <div
      role="alert"
      className="mb-6 flex items-center gap-4 rounded-lg border border-amber-200 bg-amber-50 px-5 py-4 shadow-xs"
    >
      <div className="flex size-9 flex-none items-center justify-center rounded-full bg-amber-100">
        <span className="text-base font-extrabold text-amber-600" aria-hidden>
          !
        </span>
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-amber-900">{label}</p>
        <p className="text-xs text-amber-700">
          Respóndelas para afinar tus recomendaciones.
        </p>
      </div>
      <Button variant="primary" onClick={onOpen} className="flex-none">
        <Icon name="message-circle" size={15} />
        Responder
      </Button>
    </div>
  );
}
