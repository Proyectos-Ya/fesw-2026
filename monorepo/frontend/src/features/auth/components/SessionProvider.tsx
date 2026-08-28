"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import type { UserPublic } from "../authSchema";
import { getMe, logout as logoutRequest } from "../services/authService";
import { ApiError } from "@/features/shared/api/client";

interface SessionContextValue {
  /** Usuario autenticado; null mientras carga o si la sesión es inválida. */
  user: UserPublic | null;
  isLoading: boolean;
  /** Cierra la sesión en el backend y redirige a /login. */
  logout: () => Promise<void>;
}

const SessionContext = createContext<SessionContextValue | null>(null);

/**
 * Carga el usuario autenticado desde GET /auth/me una sola vez y lo comparte
 * con toda la app. Si la cookie expiró o es inválida (401), redirige a /login.
 */
export function SessionProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<UserPublic | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    getMe()
      .then((me) => {
        if (!cancelled) setUser(me);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          router.replace("/login");
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [router]);

  const logout = useCallback(async () => {
    try {
      await logoutRequest();
    } finally {
      // Aunque el backend falle, la sesión local se considera cerrada
      router.replace("/login");
    }
  }, [router]);

  return (
    <SessionContext.Provider value={{ user, isLoading, logout }}>
      {children}
    </SessionContext.Provider>
  );
}

/** Acceso a la sesión actual; debe usarse dentro de <SessionProvider>. */
export function useSession(): SessionContextValue {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error("useSession debe usarse dentro de <SessionProvider>");
  }
  return context;
}
