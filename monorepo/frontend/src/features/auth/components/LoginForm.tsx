"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { loginSchema, type LoginData } from "../authSchema";
import { login } from "../services/authService";
import { Input } from "@/features/shared/components/Input";
import { Button } from "@/features/shared/components/Button";
import { AuthBrandPanel } from "./AuthBrandPanel";
import { ApiError } from "@/features/shared/api/client";

export function LoginForm() {
  const router = useRouter();
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
      await login(data);
      router.push("/?as=new"); // Redirect to home as a logged-in user without a profile yet
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Ocurrió un error inesperado. Inténtalo de nuevo.");
      }
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

            <div className="flex flex-col gap-2">
              <Input
                label="Contraseña"
                type="password"
                placeholder="••••••••"
                error={errors.password?.message}
                {...register("password")}
              />
              <div className="flex justify-end">
                <Link
                  href="/auth/forgot-password"
                  className="text-xs font-bold text-primary hover:text-primary-hover transition-colors"
                >
                  ¿Olvidaste tu contraseña?
                </Link>
              </div>
            </div>

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

          <Button
            variant="ghost"
            className="w-full border border-border-default hover:bg-white hover:border-border-strong text-text-strong font-bold"
          >
            ClaveÚnica
          </Button>

          <p className="text-center text-sm text-text-muted mt-10">
            ¿No tienes cuenta?{" "}
            <Link
              href="/register"
              className="font-bold text-primary hover:text-primary-hover"
            >
              Crea tu perfil gratis
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
