"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { Button } from "@/features/shared/components/Button";

import { reenviarConfirmacion } from "../services/authService";
import { AuthBrandPanel } from "./AuthBrandPanel";

/**
 * Segundos entre reenvíos.
 *
 * Coincide con `max_frequency` de `supabase/config.toml`. Si el botón permitiera
 * pulsar antes, GoTrue devolvería un 429 y el usuario leería "espera un rato"
 * sin saber cuánto; con el contador a la vista, la espera es información.
 */
const ESPERA_ENTRE_REENVIOS = 60;

function VerifyEmailNoticeInner() {
  const params = useSearchParams();
  const email = params.get("email") ?? "";
  const errorDelEnlace = params.get("error");

  const [restante, setRestante] = useState(0);
  const [estado, setEstado] = useState<"idle" | "enviando" | "enviado" | "error">(
    "idle",
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (restante <= 0) return;
    const id = setTimeout(() => setRestante((s) => s - 1), 1000);
    return () => clearTimeout(id);
  }, [restante]);

  const reenviar = async () => {
    setEstado("enviando");
    setError(null);
    try {
      await reenviarConfirmacion(email);
      setEstado("enviado");
      setRestante(ESPERA_ENTRE_REENVIOS);
    } catch (err) {
      setEstado("error");
      setError(
        err instanceof Error && err.message
          ? err.message
          : "No se pudo reenviar el correo. Inténtalo de nuevo.",
      );
    }
  };

  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-[1.1fr_1fr] bg-bg-page">
      <div className="hidden lg:block">
        <AuthBrandPanel />
      </div>

      <div className="flex items-center justify-center p-8 lg:p-12">
        <div className="w-full max-w-sm">
          <div className="eyebrow mb-2">Un paso más</div>
          <h1 className="text-4xl font-bold text-text-strong mb-2">
            Revisa tu correo
          </h1>
          <p className="text-text-muted mb-8">
            {email ? (
              <>
                Enviamos un enlace de confirmación a{" "}
                <span className="font-semibold text-text-strong">{email}</span>.
                Ábrelo para activar tu cuenta.
              </>
            ) : (
              <>
                Enviamos un enlace de confirmación a tu correo. Ábrelo para
                activar tu cuenta.
              </>
            )}
          </p>

          {errorDelEnlace && (
            <div className="mb-6 p-4 rounded-md bg-danger-soft/30 border border-danger/20 text-danger text-sm font-medium">
              El enlace no sirvió: puede haber vencido o haberse usado ya. Pide
              uno nuevo.
            </div>
          )}

          {estado === "enviado" && (
            <div className="mb-6 rounded-md bg-success-soft/40 border border-success/20 p-3 text-sm font-medium text-success">
              Listo, te enviamos otro correo.
            </div>
          )}

          {error && (
            <div className="mb-6 p-4 rounded-md bg-danger-soft/30 border border-danger/20 text-danger text-sm font-medium">
              {error}
            </div>
          )}

          {email && (
            <Button
              type="button"
              variant="ghost"
              onClick={reenviar}
              isLoading={estado === "enviando"}
              disabled={restante > 0}
              className="w-full border border-border-default hover:bg-white hover:border-border-strong text-text-strong font-bold"
            >
              {restante > 0
                ? `Reenviar en ${restante}s`
                : "Reenviar el correo de confirmación"}
            </Button>
          )}

          <p className="text-sm text-text-muted mt-8">
            ¿No lo encuentras? Mira en spam o correo no deseado. El enlace vence
            en una hora.
          </p>

          <p className="text-center text-sm text-text-muted mt-10">
            ¿Ya lo confirmaste?{" "}
            <Link
              href="/login"
              className="font-bold text-primary hover:text-primary-hover"
            >
              Inicia sesión
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}

export function VerifyEmailNotice() {
  return (
    <Suspense fallback={null}>
      <VerifyEmailNoticeInner />
    </Suspense>
  );
}
