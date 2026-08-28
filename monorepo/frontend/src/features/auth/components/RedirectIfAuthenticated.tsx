"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../AuthContext";

/**
 * Guardia inversa para las páginas de login/registro: si el usuario ya tiene
 * sesión activa, lo redirige al home en vez de mostrar el formulario.
 */
export function RedirectIfAuthenticated({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { isLoading, isAuthenticated } = useAuth();

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace("/");
    }
  }, [isLoading, isAuthenticated, router]);

  if (isLoading || isAuthenticated) {
    return (
      <div className="flex min-h-screen w-full items-center justify-center">
        <span className="text-sm text-text-subtle">Cargando…</span>
      </div>
    );
  }

  return <>{children}</>;
}
