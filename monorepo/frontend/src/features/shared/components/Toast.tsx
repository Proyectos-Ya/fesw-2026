"use client";

import { useEffect } from "react";
import { Icon } from "./Icon";

interface ToastProps {
  message: string;
  onClose: () => void;
  /** Cuánto queda a la vista antes de cerrarse solo. */
  durationMs?: number;
}

/**
 * Confirmación breve de una acción que ya terminó ("Respuesta guardada").
 * Se cierra sola y queda fija en la esquina, así se ve aunque la página esté
 * desplazada. No sirve para errores ni para avisos que piden hacer algo: esos
 * deben quedarse hasta que el usuario los lea.
 *
 * Para mostrar el mismo mensaje dos veces seguidas, quien lo usa le cambia la
 * `key`: así el temporizador vuelve a empezar.
 */
export function Toast({ message, onClose, durationMs = 4000 }: ToastProps) {
  useEffect(() => {
    const temporizador = setTimeout(onClose, durationMs);
    return () => clearTimeout(temporizador);
  }, [onClose, durationMs]);

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed inset-x-4 bottom-4 z-50 flex items-center gap-3 rounded-lg border border-primary/20 bg-teal-50 px-4 py-3 text-sm font-semibold text-teal-700 shadow-lg sm:inset-x-auto sm:right-6 sm:bottom-6 sm:max-w-sm"
    >
      <Icon name="circle-check" size={16} className="shrink-0" />
      <span className="flex-1">{message}</span>
      <button
        type="button"
        aria-label="Cerrar aviso"
        className="rounded p-0.5 hover:bg-teal-100"
        onClick={onClose}
      >
        <Icon name="x" size={14} />
      </button>
    </div>
  );
}
