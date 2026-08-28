"use client";

import { useEffect, type ReactNode } from "react";
import { useAuth } from "../AuthContext";
import { loginUrlWithReturn } from "../returnUrl";

/**
 * Guardia de rutas protegidas: redirige a /login si no hay sesión activa.
 * Se usa en los layouts de los grupos (app) y (onboarding) para cubrir
 * todas sus páginas sin repetir la lógica en cada componente.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { isLoading, isAuthenticated } = useAuth();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      // Igual que en el proxy: se guarda a dónde iba el usuario para devolverlo
      // ahí una vez autenticado.
      window.location.replace(
        loginUrlWithReturn(window.location.pathname, window.location.search),
      );
    }
  }, [isLoading, isAuthenticated]);

  if (isLoading || !isAuthenticated) {
    return (
      <div className="flex min-h-screen w-full items-center justify-center">
        <span className="text-sm text-text-subtle">Cargando…</span>
      </div>
    );
  }

  return <>{children}</>;
}
