import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { SmartQuestionCard } from "../SmartQuestionCard";
import type { Question } from "../../questionTypes";

const FREE_TEXT_Q: Question = {
  id: "q1",
  provider_id: "p1",
  discrepancy_type: null,
  tender_requirement: null,
  question: "¿Cuántos años de experiencia tienes?",
  target_profile_field: "experience_years",
  answered: false,
  answer: null,
  omitted: false,
  generated_at: "2026-06-10T00:00:00Z",
  answered_at: null,
  target_category: "general",
  options: [],
};

const CHOICE_Q: Question = {
  ...FREE_TEXT_Q,
  id: "q2",
  question: "¿En qué región operas principalmente?",
  options: ["Metropolitana", "Valparaíso", "Biobío"],
};

describe("SmartQuestionCard", () => {
  it("renders the question text", () => {
    render(
      <SmartQuestionCard question={FREE_TEXT_Q} onSubmit={vi.fn()} onOmit={vi.fn()} />,
    );
    expect(screen.getByText(FREE_TEXT_Q.question)).toBeInTheDocument();
  });

  it("renders a text input for free-text questions", () => {
    render(
      <SmartQuestionCard question={FREE_TEXT_Q} onSubmit={vi.fn()} onOmit={vi.fn()} />,
    );
    expect(screen.getByRole("textbox")).toBeInTheDocument();
  });

  it("renders radio options for multiple-choice questions", () => {
    render(
      <SmartQuestionCard question={CHOICE_Q} onSubmit={vi.fn()} onOmit={vi.fn()} />,
    );
    expect(screen.getAllByRole("radio")).toHaveLength(3);
    expect(screen.getByLabelText("Metropolitana")).toBeInTheDocument();
  });

  it("Enviar is disabled when no answer is provided", () => {
    render(
      <SmartQuestionCard question={FREE_TEXT_Q} onSubmit={vi.fn()} onOmit={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: /enviar/i })).toBeDisabled();
  });

  it("Enviar becomes enabled after typing an answer", async () => {
    render(
      <SmartQuestionCard question={FREE_TEXT_Q} onSubmit={vi.fn()} onOmit={vi.fn()} />,
    );
    await userEvent.type(screen.getByRole("textbox"), "5 años");
    expect(screen.getByRole("button", { name: /enviar/i })).toBeEnabled();
  });

  it("Enviar becomes enabled after selecting a radio option", async () => {
    render(
      <SmartQuestionCard question={CHOICE_Q} onSubmit={vi.fn()} onOmit={vi.fn()} />,
    );
    await userEvent.click(screen.getByLabelText("Valparaíso"));
    expect(screen.getByRole("button", { name: /enviar/i })).toBeEnabled();
  });

  it("calls onSubmit with the answer when Enviar is clicked", async () => {
    const onSubmit = vi.fn();
    render(
      <SmartQuestionCard question={FREE_TEXT_Q} onSubmit={onSubmit} onOmit={vi.fn()} />,
    );
    await userEvent.type(screen.getByRole("textbox"), "5 años");
    await userEvent.click(screen.getByRole("button", { name: /enviar/i }));
    expect(onSubmit).toHaveBeenCalledWith("5 años");
  });

  it("calls onOmit when Omitir is clicked", async () => {
    const onOmit = vi.fn();
    render(
      <SmartQuestionCard question={FREE_TEXT_Q} onSubmit={vi.fn()} onOmit={onOmit} />,
    );
    await userEvent.click(screen.getByRole("button", { name: /omitir/i }));
    expect(onOmit).toHaveBeenCalledOnce();
  });
});
