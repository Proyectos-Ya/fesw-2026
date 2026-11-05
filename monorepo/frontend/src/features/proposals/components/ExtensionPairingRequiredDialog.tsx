"use client";

import { Button } from "@/features/shared/components/Button";
import { Dialog } from "@/features/shared/components/Dialog";

interface ExtensionPairingRequiredDialogProps {
  open: boolean;
  busy: boolean;
  error: string | null;
  onPair: () => void;
  onRetry: () => void;
  onPostManually: () => void;
  onClose: () => void;
}

/**
 * La extensión está instalada pero no confirmó la vinculación con Chiripa. Sin vincular no
 * se abre Mercado Público con llenado asistido; el usuario puede postular a mano.
 */
export function ExtensionPairingRequiredDialog({
  open,
  busy,
  error,
  onPair,
  onRetry,
  onPostManually,
  onClose,
}: ExtensionPairingRequiredDialogProps) {
  return (
    <Dialog open={open} title="Vincula la extensión de Chiripa" onClose={onClose}>
      <div className="flex flex-col gap-4 text-sm text-text-body">
        <p>
          La extensión está instalada, pero no está vinculada a tu cuenta de Chiripa. Sin
          vincularla no podemos cargar tu borrador en Mercado Público.
        </p>

        {error && (
          <p role="alert" className="rounded-md border border-warning-border bg-warning-bg/40 p-3 text-xs text-warning-text">
            {error}
          </p>
        )}

        <div className="flex flex-wrap gap-2">
          <Button variant="primary" onClick={onPair} disabled={busy}>
            Vincular
          </Button>
          <Button variant="ghost" onClick={onRetry} disabled={busy}>
            Reintentar
          </Button>
        </div>

        <div className="border-t border-border pt-3 text-xs text-text-muted">
          <p>¿Prefieres hacerlo a mano? Abriremos Mercado Público sin completar el formulario.</p>
          <button
            type="button"
            onClick={onPostManually}
            className="mt-1 font-semibold text-primary underline-offset-2 hover:underline"
          >
            Postular manualmente
          </button>
        </div>
      </div>
    </Dialog>
  );
}
