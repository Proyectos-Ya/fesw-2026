"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { registerSchema, type RegisterData } from "../authSchema";
import { register as registerUser } from "../services/authService";
import { Input } from "@/features/shared/components/Input";
import { Button } from "@/features/shared/components/Button";
import { AuthBrandPanel } from "./AuthBrandPanel";
import { ApiError } from "@/features/shared/api/client";

export function RegisterForm() {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterData>({
    resolver: zodResolver(registerSchema),
  });

  const onSubmit = async (data: RegisterData) => {
    setIsSubmitting(true);
    setError(null);
    try {
      await registerUser(data);
      router.push("/login?registered=true");
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
          <div className="eyebrow mb-2">Comienza gratis</div>
          <h1 className="text-4xl font-bold text-text-strong mb-2">Crea tu cuenta</h1>
          <p className="text-text-muted mb-10">
            Únete a la red de proveedores inteligentes de Chile.
          </p>

          <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-5">
            {error && (
              <div className="p-4 rounded-md bg-danger-soft/30 border border-danger/20 text-danger text-sm font-medium">
                {error}
              </div>
            )}

            <Input
              label="Nombre completo"
              placeholder="Ej: Juan Pérez"
              error={errors.full_name?.message}
              {...register("full_name")}
            />

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
              placeholder="Mínimo 8 caracteres"
              error={errors.password?.message}
              {...register("password")}
            />

            <Input
              label="Teléfono (opcional)"
              placeholder="+56 9 1234 5678"
              error={errors.phone?.message}
              {...register("phone")}
            />

            <Button
              type="submit"
              variant="primary"
              className="mt-2 w-full font-bold"
              isLoading={isSubmitting}
            >
              Crear mi cuenta →
            </Button>
          </form>

          <p className="text-center text-sm text-text-muted mt-10">
            ¿Ya tienes una cuenta?{" "}
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
