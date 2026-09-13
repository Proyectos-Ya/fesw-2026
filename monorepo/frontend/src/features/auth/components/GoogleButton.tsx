"use client";

import { useState } from "react";

import { Button } from "@/features/shared/components/Button";

import { iniciarSesionConGoogle } from "../services/authService";

/**
 * Entrar con Google.
 *
 * Reemplaza al botón de ClaveÚnica que estaba puesto sin `onClick`: parecía una
 * opción disponible y no hacía nada.
 */
export function GoogleButton({
  destino,
  onError,
}: {
  destino?: string | null;
  onError?: (mensaje: string) => void;
}) {
  const [enCurso, setEnCurso] = useState(false);

  const entrar = async () => {
    setEnCurso(true);
    try {
      // Si sale bien, el navegador se va a Google y esta página deja de
      // existir; solo se vuelve de acá cuando falla.
      await iniciarSesionConGoogle(destino);
    } catch {
      onError?.("No se pudo abrir el ingreso con Google. Inténtalo de nuevo.");
      setEnCurso(false);
    }
  };

  return (
    <Button
      type="button"
      variant="ghost"
      onClick={entrar}
      isLoading={enCurso}
      className="w-full border border-border-default hover:bg-white hover:border-border-strong text-text-strong font-bold"
    >
      <span className="inline-flex items-center justify-center gap-2">
        <GoogleMark />
        Continuar con Google
      </span>
    </Button>
  );
}

function GoogleMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.91c1.7-1.57 2.69-3.88 2.69-6.62Z"
      />
      <path
        fill="#34A853"
        d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.91-2.26c-.81.54-1.84.86-3.05.86-2.35 0-4.33-1.58-5.04-3.71H.96v2.33A9 9 0 0 0 9 18Z"
      />
      <path
        fill="#FBBC05"
        d="M3.96 10.71a5.41 5.41 0 0 1 0-3.42V4.96H.96a9 9 0 0 0 0 8.08l3-2.33Z"
      />
      <path
        fill="#EA4335"
        d="M9 3.58c1.32 0 2.51.45 3.44 1.35l2.58-2.58C13.46.89 11.43 0 9 0A9 9 0 0 0 .96 4.96l3 2.33C4.67 5.16 6.65 3.58 9 3.58Z"
      />
    </svg>
  );
}
