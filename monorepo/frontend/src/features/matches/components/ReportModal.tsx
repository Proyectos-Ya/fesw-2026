"use client";

import { useState } from "react";
import { Dialog } from "@/features/shared/components/Dialog";
import { Button } from "@/features/shared/components/Button";
import { Textarea } from "@/features/shared/components/Textarea";
import { reportMatch } from "../services/tenderService";

export interface ReportModalProps {
  open: boolean;
  kind: "match" | "analysis";
  tenderId: string;
  tenderTitle?: string;
  onClose: () => void;
  onSuccess?: () => void;
}

export function ReportModal({
  open,
  kind,
  tenderId,
  tenderTitle,
  onClose,
  onSuccess,
}: ReportModalProps) {
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const isMatch = kind === "match";
  const title = isMatch ? "Reportar mal match" : "Reportar análisis incorrecto";
  const description = isMatch
    ? "Explica por qué esta licitación no se ajusta a lo que tu empresa ofrece. Al reportarla, se ajustará y dejará de recomendarse."
    : "Explica qué consideras erróneo o impreciso en la evaluación de compatibilidad realizada.";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = reason.trim();
    if (!trimmed) {
      setError("Por favor explica el motivo o las razones de tu descontento.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      await reportMatch(tenderId, { kind, reason: trimmed });
      setReason("");
      onSuccess?.();
      onClose();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Error al enviar el reporte. Inténtalo nuevamente."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} title={title} onClose={onClose}>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {tenderTitle && (
          <p className="text-xs font-semibold text-text-subtle truncate">
            Licitación: <span className="text-text-strong">{tenderTitle}</span>
          </p>
        )}
        <p className="text-sm text-text-body">{description}</p>

        {error && (
          <div role="alert" className="rounded-md bg-danger-soft p-3 text-xs text-danger">
            {error}
          </div>
        )}

        <Textarea
          label="Razón o motivo del reporte"
          placeholder="Escribe brevemente tu descontento o las razones..."
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
