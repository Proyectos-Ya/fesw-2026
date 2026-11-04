"use client";

import { useState } from "react";
import { Button } from "./Button";
import { Icon } from "./Icon";
import { Textarea } from "./Textarea";
import { NotificationSettings } from "@/features/notifications/components/NotificationSettings";
import { submitAppComment, submitAppReview } from "../services/feedbackService";

export type SettingsTab = "notificaciones" | "comentarios" | "resena";

interface SettingsHubProps {
  initialTab?: SettingsTab;
}

export function SettingsHub({ initialTab = "notificaciones" }: SettingsHubProps) {
  const [activeTab, setActiveTab] = useState<SettingsTab>(initialTab);

  // Formulario Comentarios / Quejas (S6)
  const [commentText, setCommentText] = useState("");
  const [commentLoading, setCommentLoading] = useState(false);
  const [commentSuccess, setCommentSuccess] = useState(false);
  const [commentError, setCommentError] = useState<string | null>(null);

  // Formulario Reseña (S7)
  const [rating, setRating] = useState<number | null>(null);
  const [reviewText, setReviewText] = useState("");
  const [isAnonymous, setIsAnonymous] = useState(false);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [reviewSuccess, setReviewSuccess] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);

  const handleCommentSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = commentText.trim();
    if (!trimmed) {
      setCommentError("Por favor ingresa tu mensaje, comentario o queja.");
      return;
    }
    setCommentLoading(true);
    setCommentError(null);
    try {
      await submitAppComment(trimmed);
      setCommentSuccess(true);
      setCommentText("");
    } catch (err) {
      setCommentError(
        err instanceof Error ? err.message : "Error al enviar tu comentario. Inténtalo de nuevo."
      );
    } finally {
      setCommentLoading(false);
    }
  };

  const handleReviewSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = reviewText.trim();
    if (rating === null && !trimmed) {
      setReviewError("Selecciona una calificación en estrellas o escribe un comentario.");
      return;
    }
    setReviewLoading(true);
    setReviewError(null);
    try {
      await submitAppReview({
        rating: rating !== null ? rating : undefined,
        message: trimmed || undefined,
        anonymous: isAnonymous,
      });
      setReviewSuccess(true);
      setReviewText("");
      setRating(null);
    } catch (err) {
      setReviewError(
        err instanceof Error ? err.message : "Error al enviar tu reseña. Inténtalo de nuevo."
      );
    } finally {
      setReviewLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl p-6">
      <header className="mb-6">
        <h1 className="font-display text-2xl font-bold text-text-strong">
          Ajustes y Configuración
        </h1>
        <p className="mt-1 text-sm text-text-muted">
          Administra tus canales de notificación y comparte tu retroalimentación con el equipo.
        </p>
      </header>

      {/* Selector de Pestañas */}
      <div
        role="tablist"
        aria-label="Pestañas de configuración"
        className="mb-8 flex gap-2 border-b border-border-subtle"
      >
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "notificaciones"}
          onClick={() => setActiveTab("notificaciones")}
          className={`inline-flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-semibold transition-all cursor-pointer ${
            activeTab === "notificaciones"
              ? "border-primary text-primary"
              : "border-transparent text-text-muted hover:text-text-strong"
          }`}
        >
          <Icon name="bell" className="size-4" />
          Notificaciones
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "comentarios"}
          onClick={() => setActiveTab("comentarios")}
          className={`inline-flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-semibold transition-all cursor-pointer ${
            activeTab === "comentarios"
              ? "border-primary text-primary"
              : "border-transparent text-text-muted hover:text-text-strong"
          }`}
        >
          <Icon name="message-square" className="size-4" />
          Comentarios y Quejas
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "resena"}
          onClick={() => setActiveTab("resena")}
          className={`inline-flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-semibold transition-all cursor-pointer ${
            activeTab === "resena"
              ? "border-primary text-primary"
              : "border-transparent text-text-muted hover:text-text-strong"
          }`}
        >
          <Icon name="star" className="size-4" />
          Dejar Reseña
        </button>
      </div>

      {/* Contenido de la Pestaña Activa */}
      {activeTab === "notificaciones" && <NotificationSettings />}

      {activeTab === "comentarios" && (
        <div className="rounded-lg border border-border-subtle bg-surface-card p-6 shadow-xs">
          <h2 className="font-display text-lg font-semibold text-text-strong">
            Mensajes, comentarios o quejas del sistema
          </h2>
          <p className="mt-1 text-sm text-text-muted">
            Cuéntanos qué funciona bien, qué podemos mejorar o cualquier incidencia que hayas
            experimentado. Tu opinión nos ayuda directamente a afinar Chiripa.
          </p>

          {commentSuccess ? (
            <div
              role="alert"
              className="mt-6 flex items-start gap-3 rounded-lg border border-primary/20 bg-primary-soft p-4 text-sm text-text-strong"
            >
              <Icon name="circle-check" className="size-5 text-primary shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold mb-0.5">¡Gracias por tu mensaje!</p>
                <p className="text-xs text-text-muted">
                  Tu comentario o queja ha sido registrado exitosamente y será revisado por nuestro
                  equipo.
                </p>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setCommentSuccess(false)}
                  className="mt-3 text-xs"
                >
                  Enviar otro comentario
                </Button>
              </div>
            </div>
          ) : (
            <form onSubmit={handleCommentSubmit} className="mt-6 flex flex-col gap-4">
              {commentError && (
                <div role="alert" className="rounded-md bg-danger-soft p-3 text-xs text-danger">
                  {commentError}
                </div>
              )}

              <Textarea
                label="Mensaje, comentario o queja"
                placeholder="Escribe tu mensaje, inquietud, reclamo o sugerencia..."
                value={commentText}
                onChange={(e) => setCommentText(e.target.value)}
                rows={5}
                required
                maxLength={2000}
              />

              <div className="flex justify-end">
                <Button
                  type="submit"
                  variant="primary"
                  isLoading={commentLoading}
                  disabled={!commentText.trim()}
                >
                  Enviar comentario
                </Button>
              </div>
            </form>
          )}
        </div>
      )}

      {activeTab === "resena" && (
        <div className="rounded-lg border border-border-subtle bg-surface-card p-6 shadow-xs">
          <h2 className="font-display text-lg font-semibold text-text-strong">
            Deja una reseña del sistema
          </h2>
          <p className="mt-1 text-sm text-text-muted">
            Evalúa tu experiencia con Chiripa asignando una calificación en estrellas (0 a 5) y/o
            escribiendo un comentario opcional.
          </p>

          {reviewSuccess ? (
            <div
              role="alert"
              className="mt-6 flex items-start gap-3 rounded-lg border border-primary/20 bg-primary-soft p-4 text-sm text-text-strong"
            >
              <Icon name="circle-check" className="size-5 text-primary shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold mb-0.5">¡Gracias por tu reseña!</p>
                <p className="text-xs text-text-muted">
                  Agradecemos el tiempo que te tomaste para valorar la plataforma.
                </p>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setReviewSuccess(false)}
                  className="mt-3 text-xs"
                >
                  Enviar otra reseña
                </Button>
              </div>
            </div>
          ) : (
            <form onSubmit={handleReviewSubmit} className="mt-6 flex flex-col gap-5">
              {reviewError && (
                <div role="alert" className="rounded-md bg-danger-soft p-3 text-xs text-danger">
                  {reviewError}
                </div>
              )}

              {/* Selector de Estrellas (0 a 5) */}
              <div>
                <label className="block text-xs font-bold uppercase tracking-caps text-text-subtle mb-2">
                  Calificación (0 a 5 estrellas)
                </label>
                <div className="flex items-center gap-1.5" aria-label="Calificación en estrellas">
                  <button
                    type="button"
                    onClick={() => setRating(0)}
                    aria-label="0 estrellas"
                    className={`px-2 py-1 text-xs rounded border transition-colors cursor-pointer ${
                      rating === 0
                        ? "bg-primary text-text-inverse border-primary"
                        : "border-border-subtle text-text-muted hover:bg-surface-hover"
                    }`}
                  >
                    0 estrellas
                  </button>
                  {[1, 2, 3, 4, 5].map((star) => (
                    <button
                      key={star}
                      type="button"
                      onClick={() => setRating(star)}
                      aria-label={`${star} estrellas`}
                      className="p-1.5 transition-transform hover:scale-110 cursor-pointer"
                    >
                      <Icon
                        name="star"
                        className={`size-6 ${
                          rating !== null && rating >= star
                            ? "fill-amber-400 text-amber-400"
                            : "text-border-strong hover:text-text-muted"
                        }`}
                      />
                    </button>
                  ))}
                  {rating !== null && (
                    <span className="ml-2 text-xs font-medium text-text-muted">
                      ({rating} de 5)
                    </span>
                  )}
                </div>
              </div>

              {/* Comentario opcional */}
              <Textarea
                label="Comentario opcional"
                placeholder="Cuéntanos con mayor detalle qué te parece la plataforma..."
                value={reviewText}
                onChange={(e) => setReviewText(e.target.value)}
                rows={4}
                maxLength={2000}
              />

              {/* Opción de anonimato */}
              <div className="flex items-center gap-2">
                <input
                  id="anonymous-review"
                  type="checkbox"
                  checked={isAnonymous}
                  onChange={(e) => setIsAnonymous(e.target.checked)}
                  className="size-4 rounded border-border-strong text-primary focus:ring-primary/40 cursor-pointer"
                />
                <label
                  htmlFor="anonymous-review"
                  className="text-sm font-medium text-text-body cursor-pointer select-none"
                >
                  Publicar de forma anónima
                </label>
              </div>

              <div className="flex justify-end">
                <Button
                  type="submit"
                  variant="primary"
                  isLoading={reviewLoading}
                  disabled={rating === null && !reviewText.trim()}
                >
                  Enviar reseña
                </Button>
              </div>
            </form>
          )}
        </div>
      )}
    </div>
  );
}
