"use client";

import { useEffect, useState } from "react";
import { getSmartQuestions } from "../services/questionService";
import type { Question } from "../questionTypes";

interface SmartQuestionsState {
  questions: Question[];
  loading: boolean;
}

export function useSmartQuestions(
  tenderId?: string,
  enabled: boolean = true
): SmartQuestionsState {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Si enabled es falso o si se pasa una cadena vacía explícitamente, se omite la consulta
    if (!enabled || tenderId === "") return;

    let cancelled = false;
    setLoading(true);

    void getSmartQuestions(tenderId)
      .then((all) => {
        if (cancelled) return;
        setQuestions(all.filter((q) => !q.answered && !q.omitted));
      })
      .catch(() => {
        if (cancelled) return;
        setQuestions([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [tenderId, enabled]);

  return { questions, loading };
}
