import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { SmartQuestionsBanner } from "../SmartQuestionsBanner";
import type { Question } from "../../questionTypes";

const Q = (id: string): Question => ({
  id,
  provider_id: "p1",
  discrepancy_type: null,
  tender_requirement: null,
  question: "¿Pregunta?",
  target_profile_field: "field",
  answered: false,
  answer: null,
  omitted: false,
  generated_at: "2026-06-10T00:00:00Z",
  answered_at: null,
  target_category: "general",
  options: [],
});

describe("SmartQuestionsBanner", () => {
  it("renders nothing when there are no questions", () => {
    const { container } = render(
      <SmartQuestionsBanner questions={[]} onOpen={vi.fn()} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders the banner when questions exist", () => {
    render(<SmartQuestionsBanner questions={[Q("q1")]} onOpen={vi.fn()} />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText(/pregunta/i)).toBeInTheDocument();
  });

  it("calls onOpen when the CTA button is clicked", async () => {
    const onOpen = vi.fn();
    render(<SmartQuestionsBanner questions={[Q("q1")]} onOpen={onOpen} />);
    await userEvent.click(screen.getByRole("button"));
    expect(onOpen).toHaveBeenCalledOnce();
  });

  it("shows the pending question count", () => {
    render(<SmartQuestionsBanner questions={[Q("q1"), Q("q2")]} onOpen={vi.fn()} />);
    expect(screen.getByText(/2/)).toBeInTheDocument();
  });
});
