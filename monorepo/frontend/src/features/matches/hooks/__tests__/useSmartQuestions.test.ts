import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { useSmartQuestions } from "../useSmartQuestions";
import type { Question } from "../../questionTypes";

vi.mock("../../services/questionService");
import * as questionService from "../../services/questionService";

const Q = (overrides: Partial<Question> = {}): Question => ({
  id: "q1",
  provider_id: "p1",
  discrepancy_type: null,
  tender_requirement: null,
  question: "¿Cuál es tu experiencia?",
  target_profile_field: "experience",
  answered: false,
  answer: null,
  omitted: false,
  generated_at: "2026-06-10T00:00:00Z",
  answered_at: null,
  target_category: "general",
  options: [],
  ...overrides,
});

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useSmartQuestions", () => {
  it("starts in loading state", () => {
    vi.mocked(questionService.getSmartQuestions).mockReturnValue(new Promise(() => {}));
    const { result } = renderHook(() => useSmartQuestions("profile-1"));
    expect(result.current.loading).toBe(true);
    expect(result.current.questions).toEqual([]);
  });

  it("returns only unanswered and non-omitted questions", async () => {
    const questions = [
      Q({ id: "q1", answered: false, omitted: false }),
      Q({ id: "q2", answered: true, omitted: false }),
      Q({ id: "q3", answered: false, omitted: true }),
    ];
    vi.mocked(questionService.getSmartQuestions).mockResolvedValue(questions);

    const { result } = renderHook(() => useSmartQuestions("profile-1"));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.questions).toHaveLength(1);
    expect(result.current.questions[0].id).toBe("q1");
  });

  it("returns empty list on fetch error without throwing", async () => {
    vi.mocked(questionService.getSmartQuestions).mockRejectedValue(new Error("network"));
    const { result } = renderHook(() => useSmartQuestions("profile-1"));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.questions).toEqual([]);
  });

  it("does not fetch when profileId is empty", () => {
    const { result } = renderHook(() => useSmartQuestions(""));
    expect(result.current.loading).toBe(false);
    expect(questionService.getSmartQuestions).not.toHaveBeenCalled();
  });
});
