import React from "react";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { HomeDashboard } from "../HomeDashboard";
import * as tenderService from "../../services/tenderService";
import * as questionService from "../../services/questionService";
import * as useSmartQuestionsHook from "../../hooks/useSmartQuestions";
import type { Question } from "../../questionTypes";

const STABLE_ROUTER = { replace: vi.fn(), push: vi.fn() };
const STABLE_USER = { id: "u-1", email: "usuario@empresa.cl", full_name: "Usuario" };

vi.mock("next/navigation", () => ({
  useRouter: () => STABLE_ROUTER,
}));

vi.mock("@/features/auth/AuthContext", () => ({
  useAuth: () => ({ user: STABLE_USER, isLoading: false, isAuthenticated: true }),
}));

vi.mock("@/features/workspaces/WorkspaceContext", () => ({
  useWorkspace: () => ({
    workspaces: [],
    recentWorkspaces: [],
    activeWorkspace: null,
  }),
}));

vi.mock("../../services/tenderService", () => ({
  getRecommendedTenders: vi.fn(),
}));

vi.mock("../../services/questionService", () => ({
  answerSmartQuestion: vi.fn(),
}));

vi.mock("@/features/ranking-telemetry/services/rankingTelemetryService", () => ({
  reportTenderInteraction: vi.fn(),
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: React.ComponentProps<"a"> & { href: string }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

const MOCK_QUESTIONS: Question[] = [
  {
    id: "q-1",
    question: "¿Dispone de certificación ISO 9001?",
    target_keyword: "certificacion:iso_9001",
    supplier_id: "sup-1",
    tender_id: null,
    status: "pending",
    created_at: "2026-06-01T00:00:00Z",
  },
  {
    id: "q-2",
    question: "¿Dispone de camión aljibe de 10.000 litros?",
    target_keyword: "maquinaria:camion_aljibe",
    supplier_id: "sup-1",
    tender_id: null,
    status: "pending",
    created_at: "2026-06-01T00:00:00Z",
  },
];

describe("HomeDashboard: Flujo e Interacción de Preguntas Inteligentes", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(tenderService.getRecommendedTenders).mockResolvedValue([]);
  });

  it("muestra el banner y al hacer clic en 'Responder' oculta el banner y muestra la tarjeta con progreso '1/2'", async () => {
    vi.spyOn(useSmartQuestionsHook, "useSmartQuestions").mockReturnValue({
      questions: MOCK_QUESTIONS,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<HomeDashboard />);

    // 1. Banner visible, tarjeta no visible
    expect(
      await screen.findByText(/tienes 2 preguntas pendientes para mejorar tus matches/i),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("question-progress")).not.toBeInTheDocument();

    // 2. Clic en "Responder"
    const responderBtn = screen.getByRole("button", { name: /responder/i });
    await userEvent.click(responderBtn);

    // 3. Banner desaparece, tarjeta visible con la primera pregunta y progreso 1/2
    expect(
      screen.queryByText(/tienes 2 preguntas pendientes para mejorar tus matches/i),
    ).not.toBeInTheDocument();
    expect(screen.getByText("¿Dispone de certificación ISO 9001?")).toBeInTheDocument();
    expect(screen.getByTestId("question-progress")).toHaveTextContent("1/2");
  });

  it("avanza de la pregunta 1 a la 2 con progreso '2/2' al responder y se cierra al terminar", async () => {
    vi.spyOn(useSmartQuestionsHook, "useSmartQuestions").mockReturnValue({
      questions: MOCK_QUESTIONS,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    vi.mocked(questionService.answerSmartQuestion).mockResolvedValue({
      status: "ok",
      detail: "Guardado",
    });

    render(<HomeDashboard />);

    // Abrir tarjeta
    const responderBtn = await screen.findByRole("button", { name: /responder/i });
    await userEvent.click(responderBtn);

    // Responder primera pregunta
    const yesBtn = screen.getByRole("button", { name: /sí, lo tengo/i });
    await userEvent.click(yesBtn);

    // Esperar a que la tarjeta avance a la pregunta 2 (progreso 2/2)
    await waitFor(
      () => {
        expect(
          screen.getByText("¿Dispone de camión aljibe de 10.000 litros?"),
        ).toBeInTheDocument();
      },
      { timeout: 2000 },
    );
    expect(screen.getByTestId("question-progress")).toHaveTextContent("2/2");

    // Responder segunda pregunta ("No, descartar")
    const noBtn = screen.getByRole("button", { name: /no, descartar/i });
    await userEvent.click(noBtn);

    // Al responder la última pregunta, la tarjeta desaparece
    await waitFor(
      () => {
        expect(
          screen.queryByText("¿Dispone de camión aljibe de 10.000 litros?"),
        ).not.toBeInTheDocument();
      },
      { timeout: 2000 },
    );

    // Se verifica que no quede ni banner ni tarjeta
    expect(screen.queryByTestId("question-progress")).not.toBeInTheDocument();
    expect(
      screen.queryByText(/tienes 2 preguntas pendientes para mejorar tus matches/i),
    ).not.toBeInTheDocument();
  });
});
