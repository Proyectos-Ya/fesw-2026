"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../AuthContext";

/**
 * Guardia de rutas protegidas: redirige a /login si no hay sesión activa.
 * Se usa en los layouts de los grupos (app) y (onboarding) para cubrir
 * todas sus páginas sin repetir la lógica en cada componente.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { isLoading, isAuthenticated } = useAuth();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isLoading, isAuthenticated, router]);

  if (isLoading || !isAuthenticated) {
    return (
      <div className="flex min-h-screen w-full items-center justify-center">
        <span className="text-sm text-text-subtle">Cargando…</span>
      </div>
    );
  }

  return <>{children}</>;
}
