"use client";

import { useEffect, useState } from "react";
import { getSmartQuestions } from "../services/questionService";
import type { Question } from "../questionTypes";

interface SmartQuestionsState {
  questions: Question[];
  loading: boolean;
}

export function useSmartQuestions(profileId: string): SmartQuestionsState {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!profileId) return;

    let cancelled = false;
    setLoading(true);

    void getSmartQuestions(profileId)
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
  }, [profileId]);

  return { questions, loading };
}
