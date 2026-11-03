"use client";

import { Button } from "@/features/shared/components/Button";
import { Icon } from "@/features/shared/components/Icon";

interface PostularEnMercadoPublicoButtonProps {
  canWrite: boolean;
  isExpired: boolean;
  busy: boolean;
  onClick: () => void;
  className?: string;
}

/**
 * Botón principal para activar la postulación asistida en Mercado Público (CA1).
 */
export function PostularEnMercadoPublicoButton({
  canWrite,
  isExpired,
  busy,
  onClick,
  className = "",
}: PostularEnMercadoPublicoButtonProps) {
  let disabledReason: string | null = null;
  if (isExpired) {
    disabledReason = "La licitación ya cerró su plazo de postulación.";
  } else if (!canWrite) {
    disabledReason = "Tu rol no permite postular ni modificar propuestas.";
  }

  const isDisabled = Boolean(disabledReason) || busy;

  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      <Button
        variant="primary"
        className="px-4 py-2 text-sm font-semibold shadow-md"
        disabled={isDisabled}
        onClick={onClick}
        aria-label="Postular en Mercado Público"
      >
        {busy ? (
          <>
            <Icon name="refresh-cw" size={16} className="animate-spin" />
            Conectando con Mercado Público...
          </>
        ) : (
          <>
            <Icon name="external-link" size={16} />
            Postular en Mercado Público
          </>
        )}
      </Button>

      {disabledReason && (
        <span className="text-xs text-text-muted">{disabledReason}</span>
      )}
    </div>
  );
}
