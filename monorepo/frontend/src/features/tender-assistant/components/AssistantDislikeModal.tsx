"use client";

import { useState } from "react";
import { Dialog } from "@/features/shared/components/Dialog";
import { Button } from "@/features/shared/components/Button";
import { Textarea } from "@/features/shared/components/Textarea";
import { submitAssistantDislike } from "../services/tenderAssistantService";

export interface AssistantDislikeModalProps {
  open: boolean;
  tenderId: string;
  messageId: string;
  onClose: () => void;
  onSuccess?: () => void;
}

export function AssistantDislikeModal({
  open,
  tenderId,
  messageId,
  onClose,
  onSuccess,
}: AssistantDislikeModalProps) {
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = reason.trim();
    if (!trimmed) {
      setError("Por favor explica las razones de tu descontento con la respuesta.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      await submitAssistantDislike(tenderId, messageId, trimmed);
      setReason("");
      onSuccess?.();
      onClose();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Error al registrar el reporte. Inténtalo de nuevo."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} title="Reportar respuesta del asistente" onClose={onClose}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <p className="text-sm text-text-body">
          Explica qué consideras erróneo o inadecuado en esta respuesta. El asistente acogerá tus
          comentarios en las próximas consultas de esta licitación.
        </p>

        {error && (
          <div role="alert" className="rounded-md bg-danger-soft p-3 text-xs text-danger">
            {error}
          </div>
        )}

        <Textarea
          label="Razón o motivo del descontento"
          placeholder="Ej: El plazo indicado no coincide con las bases, omitió las garantías..."
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={4}
          required
          maxLength={1000}
        />

        <div className="mt-2 flex items-center justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose} disabled={loading}>
            Cancelar
          </Button>
          <Button type="submit" variant="primary" isLoading={loading} disabled={!reason.trim()}>
            Enviar reporte
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
