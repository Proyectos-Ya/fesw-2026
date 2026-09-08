"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { loginSchema, type LoginData } from "../authSchema";
import { iniciarSesionConCorreo } from "../services/authService";
import { useAuth } from "../AuthContext";
import { RETURN_URL_PARAM, sanitizeReturnUrl } from "../returnUrl";
import { Input } from "@/features/shared/components/Input";
import { Button } from "@/features/shared/components/Button";
import { AuthBrandPanel } from "./AuthBrandPanel";
import { GoogleButton } from "./GoogleButton";

/**
 * Traduce los errores de Supabase Auth a algo accionable.
 *
 * El caso que importa es "Email not confirmed": con la confirmación de correo
 * encendida, GoTrue rechaza el inicio de sesión hasta que se abra el enlace, y
 * el mensaje en inglés no le dice a nadie qué hacer.
 */
function mensajeDeError(err: unknown): string {
  const mensaje = err instanceof Error ? err.message : "";
  if (/email not confirmed/i.test(mensaje)) {
    return "Todavía no confirmas tu correo. Revisa tu bandeja de entrada y abre el enlace que te enviamos.";
  }
  if (/invalid login credentials/i.test(mensaje)) {
    return "Correo o contraseña incorrectos.";
  }
  return mensaje || "Ocurrió un error inesperado. Inténtalo de nuevo.";
}

/**
 * Errores que llegan por la URL, no del formulario.
 *
 * Los escriben `/auth/callback` y `/auth/confirm` cuando el canje falla: sin
 * esto, alguien que cancela en la pantalla de Google vuelve al login sin la más
 * mínima señal de que algo pasó.
 */
function BannerDeErrorEnLaUrl() {
  const params = useSearchParams();
  const error = params.get("error");
  if (!error) return null;
  return (
    <div className="mb-6 p-4 rounded-md bg-danger-soft/30 border border-danger/20 text-danger text-sm font-medium">
      {error === "sin_codigo" || error === "enlace_invalido"
        ? "El enlace no sirvió. Puede haber vencido o haberse usado ya."
        : "No se pudo completar el ingreso. Inténtalo de nuevo."}
    </div>
  );
}

function LoginFormInner() {
  const router = useRouter();
  const params = useSearchParams();
  const { refresh } = useAuth();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginData>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginData) => {
    setIsSubmitting(true);
    setError(null);
    try {
      await iniciarSesionConCorreo(data);
      await refresh();
      // Vuelve a donde el usuario quería ir —el enlace de una alerta, por
      // ejemplo— en vez de aterrizar siempre en el home. `sanitizeReturnUrl`
      // descarta destinos externos.
      router.push(sanitizeReturnUrl(params.get(RETURN_URL_PARAM)) ?? "/");
    } catch (err) {
      setError(mensajeDeError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-[1.1fr_1fr] bg-bg-page">
      <div className="hidden lg:block">
        <AuthBrandPanel />
      </div>

      <div className="flex items-center justify-center p-8 lg:p-12">
        <div className="w-full max-w-sm">
          <div className="eyebrow mb-2">Bienvenido de vuelta</div>
          <h1 className="text-4xl font-bold text-text-strong mb-2">Inicia sesión</h1>
          <p className="text-text-muted mb-10">
            Entra para ver tus licitaciones compatibles de hoy.
          </p>

          <BannerDeErrorEnLaUrl />

          <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-5">
            {error && (
              <div className="p-4 rounded-md bg-danger-soft/30 border border-danger/20 text-danger text-sm font-medium">
                {error}
              </div>
            )}

            <Input
              label="Correo electrónico"
              type="email"
              placeholder="tu@correo.cl"
              error={errors.email?.message}
              {...register("email")}
            />

            <Input
              label="Contraseña"
              type="password"
              placeholder="••••••••"
              error={errors.password?.message}
              {...register("password")}
            />

            <Button
              type="submit"
              variant="primary"
              className="mt-2 w-full font-bold"
              isLoading={isSubmitting}
            >
              Iniciar sesión →
            </Button>
          </form>

          <div className="flex items-center gap-4 my-8">
            <div className="h-px flex-1 bg-border-subtle" />
            <span className="text-[10px] font-bold uppercase tracking-caps text-text-subtle">
              o continúa con
            </span>
            <div className="h-px flex-1 bg-border-subtle" />
          </div>

          <GoogleButton
            destino={sanitizeReturnUrl(params.get(RETURN_URL_PARAM))}
            onError={setError}
          />

          <p className="text-center text-sm text-text-muted mt-10">
            ¿No tienes cuenta?{" "}
            <Link
              href="/register"
              className="font-bold text-primary hover:text-primary-hover"
            >
              Crea tu perfil gratis
            </Link>
          </p>

          <p className="text-center text-xs text-text-subtle mt-6">
            Al continuar aceptas nuestra{" "}
            <Link
              href="/privacidad"
              className="underline hover:text-text-muted"
            >
              política de privacidad
            </Link>
            .
          </p>
        </div>
      </div>
    </div>
  );
}

export function LoginForm() {
  return (
    <Suspense fallback={null}>
      <LoginFormInner />
    </Suspense>
  );
}
