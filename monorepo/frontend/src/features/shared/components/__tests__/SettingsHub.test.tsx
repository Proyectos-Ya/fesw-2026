import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { SettingsHub } from "../SettingsHub";
import * as feedbackService from "../../services/feedbackService";

// Mock NotificationSettings
vi.mock("@/features/notifications/components/NotificationSettings", () => ({
  NotificationSettings: () => <div data-testid="notification-settings">Preferencias de Alertas</div>,
}));

describe("SettingsHub (HU-24, S6/S7)", () => {
  it("renderiza las pestañas de Notificaciones, Comentarios y Reseña", () => {
    render(<SettingsHub initialTab="notificaciones" />);
    expect(screen.getByRole("tab", { name: /Notificaciones/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Comentarios y Quejas/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Dejar Reseña/i })).toBeInTheDocument();
  });

  it("permite enviar un mensaje, comentario o queja (S6)", async () => {
    const commentSpy = vi.spyOn(feedbackService, "submitAppComment").mockResolvedValueOnce({
      id: "c-1",
      user_id: "u-1",
      kind: "comment",
      message: "El sistema carga muy rápido.",
      anonymous: false,
      created_at: "2026-10-27T10:00:00Z",
    });

    render(<SettingsHub initialTab="comentarios" />);

    const textarea = screen.getByLabelText(/Mensaje, comentario o queja/i);
    fireEvent.change(textarea, { target: { value: "El sistema carga muy rápido." } });

    const submitBtn = screen.getByRole("button", { name: /Enviar comentario/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(commentSpy).toHaveBeenCalledWith("El sistema carga muy rápido.");
      expect(screen.getByText(/¡Gracias por tu mensaje!/i)).toBeInTheDocument();
    });
  });

  it("permite enviar una reseña con estrellas, comentario y anonimato (S7)", async () => {
    const reviewSpy = vi.spyOn(feedbackService, "submitAppReview").mockResolvedValueOnce({
      id: "r-1",
      user_id: "u-1",
      kind: "review",
      rating: 5,
      message: "Excelente plataforma.",
      anonymous: true,
      created_at: "2026-10-27T10:00:00Z",
    });

    render(<SettingsHub initialTab="resena" />);

    // Click 5 estrellas
    const star5 = screen.getByRole("button", { name: /5 estrellas/i });
    fireEvent.click(star5);

    const textarea = screen.getByLabelText(/Comentario opcional/i);
    fireEvent.change(textarea, { target: { value: "Excelente plataforma." } });

    const anonCheckbox = screen.getByLabelText(/Publicar de forma anónima/i);
    fireEvent.click(anonCheckbox);

    const submitBtn = screen.getByRole("button", { name: /Enviar reseña/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(reviewSpy).toHaveBeenCalledWith({
        rating: 5,
        message: "Excelente plataforma.",
        anonymous: true,
      });
      expect(screen.getByText(/¡Gracias por tu reseña!/i)).toBeInTheDocument();
    });
  });
});
