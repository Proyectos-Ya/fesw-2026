import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { SmartQuestionCard } from "../SmartQuestionCard";
import type { DynamicQuestionDTO } from "../../questionTypes";
import * as questionService from "../../services/questionService";

const MOCK_QUESTION: DynamicQuestionDTO = {
  id: "q-12345",
  question: "¿Dispones de camiones pluma con capacidad superior a 10 toneladas?",
  target_keyword: "maquinaria:camion_pluma",
};

describe("SmartQuestionCard (Fase 4)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renderiza el texto de la pregunta, la insignia de IA y la keyword objetivo", () => {
    render(<SmartQuestionCard question={MOCK_QUESTION} onAnswered={vi.fn()} />);

    expect(screen.getByText(MOCK_QUESTION.question)).toBeInTheDocument();
    expect(screen.getByText(/pregunta inteligente/i)).toBeInTheDocument();
    expect(screen.getByText(MOCK_QUESTION.target_keyword)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /sí, lo tengo/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /no, descartar/i }),
    ).toBeInTheDocument();
  });

  it("muestra el contador de progreso 'actual/total' en la parte inferior izquierda", () => {
    render(
      <SmartQuestionCard
        question={MOCK_QUESTION}
        progress={{ current: 1, total: 3 }}
        onAnswered={vi.fn()}
      />,
    );

    const progressEl = screen.getByTestId("question-progress");
    expect(progressEl).toBeInTheDocument();
    expect(progressEl).toHaveTextContent("1/3");
  });

  it("envía 'Sí' al hacer clic en 'Sí, lo tengo', muestra estado de éxito y llama a onAnswered", async () => {
    const onAnswered = vi.fn();
    const answerSpy = vi
      .spyOn(questionService, "answerSmartQuestion")
      .mockResolvedValueOnce({ status: "ok", detail: "Guardado" });

    render(<SmartQuestionCard question={MOCK_QUESTION} onAnswered={onAnswered} />);

    const yesButton = screen.getByRole("button", { name: /sí, lo tengo/i });
    await userEvent.click(yesButton);

    expect(answerSpy).toHaveBeenCalledWith({
      question_id: "q-12345",
      answer: "Sí",
    });

    // Se muestra el feedback de éxito
    await waitFor(() => {
      expect(
        screen.getByText(/¡respuesta registrada con éxito!/i),
      ).toBeInTheDocument();
    });

    // Esperar a que el timeout invoque la prop de salida
    await waitFor(
      () => {
        expect(onAnswered).toHaveBeenCalledWith("q-12345");
      },
      { timeout: 1500 },
    );
  });

  it("envía 'No' al hacer clic en 'No, descartar' y procesa el descarte", async () => {
    const onAnswered = vi.fn();
    const answerSpy = vi
      .spyOn(questionService, "answerSmartQuestion")
      .mockResolvedValueOnce({ status: "ok", detail: "Descartado" });

    render(<SmartQuestionCard question={MOCK_QUESTION} onAnswered={onAnswered} />);

    const noButton = screen.getByRole("button", { name: /no, descartar/i });
    await userEvent.click(noButton);

    expect(answerSpy).toHaveBeenCalledWith({
      question_id: "q-12345",
      answer: "No",
    });

    await waitFor(() => {
      expect(
        screen.getByText(/¡respuesta registrada con éxito!/i),
      ).toBeInTheDocument();
    });

    await waitFor(
      () => {
        expect(onAnswered).toHaveBeenCalledWith("q-12345");
      },
      { timeout: 1500 },
    );
  });

  it("muestra mensaje de error y no invoca onAnswered cuando la API falla", async () => {
    const onAnswered = vi.fn();
    vi.spyOn(questionService, "answerSmartQuestion").mockRejectedValueOnce(
      new Error("Fallo de red en el servidor"),
    );

    render(<SmartQuestionCard question={MOCK_QUESTION} onAnswered={onAnswered} />);

    const yesButton = screen.getByRole("button", { name: /sí, lo tengo/i });
    await userEvent.click(yesButton);

    await waitFor(() => {
      expect(
        screen.getByText(/fallo de red en el servidor/i),
      ).toBeInTheDocument();
    });

    expect(onAnswered).not.toHaveBeenCalled();
    // Botones deben reactivarse para permitir reintentar
    expect(
      screen.getByRole("button", { name: /sí, lo tengo/i }),
    ).toBeEnabled();
  });
});
