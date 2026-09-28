"use client";

import { useEffect, useState } from "react";

export type CreatingCompanyPhase = "creating" | "verifying";

/**
 * Cuándo cambia el mensaje. Crear una empresa tarda entre 0,2 s y casi un minuto
 * según esté despierto el proveedor de embeddings (medido en producción): sin
 * estos cambios, un envío lento es indistinguible de una pantalla colgada, y lo
 * que hace el usuario entonces es recargar y reintentar.
 */
const ANALYZING_AFTER_MS = 4_000;
const SLOW_AFTER_MS = 20_000;

const MESSAGES = {
  creating: "Creando tu empresa…",
  analyzing: "Analizando tu perfil para encontrar licitaciones compatibles…",
  slow: "Está tardando más de lo normal. Seguimos trabajando, no cierres esta página.",
  verifying: "Confirmando que tu empresa quedó registrada…",
} as const;

type Stage = "creating" | "analyzing" | "slow";

interface CreatingCompanyViewProps {
  phase: CreatingCompanyPhase;
}

/** Pantalla de espera mientras se crea la empresa, visible desde el clic. */
export function CreatingCompanyView({ phase }: CreatingCompanyViewProps) {
  const [stage, setStage] = useState<Stage>("creating");

  useEffect(() => {
    const analyzing = setTimeout(() => setStage("analyzing"), ANALYZING_AFTER_MS);
    const slow = setTimeout(() => setStage("slow"), SLOW_AFTER_MS);
    return () => {
      clearTimeout(analyzing);
      clearTimeout(slow);
    };
  }, []);

  const message = phase === "verifying" ? MESSAGES.verifying : MESSAGES[stage];

  return (
    <div className="flex flex-col items-center justify-center gap-6 py-12 text-center">
      <div className="flex h-20 w-20 items-center justify-center rounded-full bg-primary-soft">
        <span
          aria-hidden="true"
          className="h-10 w-10 animate-spin rounded-full border-4 border-primary border-t-transparent"
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <h2 className="font-display text-2xl font-bold text-text-primary">
          Estamos creando tu empresa
        </h2>
        <p role="status" aria-live="polite" className="text-sm text-text-muted">
          {message}
        </p>
      </div>

      {/* Barra indeterminada: no hay forma honesta de estimar cuánto falta. */}
      <div className="h-1 w-48 overflow-hidden rounded-full bg-border-subtle/50">
        <div className="h-full w-1/3 animate-pulse rounded-full bg-primary" />
      </div>
    </div>
  );
}
