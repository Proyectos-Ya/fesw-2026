"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { ApiError, registrarProveedorDeToken } from "@/features/shared/api/client";

import type { UserPublic } from "./authSchema";
import { cerrarSesion, getMe } from "./services/authService";
import { crearClienteNavegador } from "./supabase/client";

interface AuthContextValue {
  user: UserPublic | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  /** Si la dirección de correo está confirmada en el proveedor. */
  emailVerified: boolean;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserPublic | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const cargarPerfil = useCallback(async () => {
    try {
      setUser(await getMe());
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        // La sesión de Supabase existe pero el backend no la acepta: token
        // vencido, cuenta desactivada. Se cierra acá para no dejar al usuario
        // rebotando entre una sesión que el navegador cree tener y una API que
        // la rechaza. Esto reemplaza al viejo CookieCleanupMiddleware, que
        // borraba la cookie desde el backend y ya no puede: la de Supabase la
        // escribe el navegador y el backend no la conoce.
        await cerrarSesion();
      } else if (process.env.NODE_ENV !== "production") {
        console.warn("[AuthContext] /auth/me falló:", err);
      }
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await cerrarSesion();
    } finally {
      setUser(null);
    }
  }, []);

  useEffect(() => {
    const supabase = crearClienteNavegador();

    // El resto de la aplicación llama a la API por `apiFetch`, que no conoce a
    // esta feature: acá se le entrega de dónde sacar el token.
    registrarProveedorDeToken(async () => {
      const { data } = await supabase.auth.getSession();
      return data.session?.access_token ?? null;
    });

    // `onAuthStateChange` dispara también con la sesión que ya había al cargar
    // la página, así que cubre el arranque y no hace falta una carga aparte.
    const { data } = supabase.auth.onAuthStateChange((evento, sesion) => {
      if (!sesion) {
        setUser(null);
        setIsLoading(false);
        return;
      }
      // TOKEN_REFRESHED llega cada hora y no cambia quién es el usuario:
      // recargar el perfil ahí sería una petición por hora y por pestaña.
      if (evento === "TOKEN_REFRESHED") return;
      void cargarPerfil();
    });

    return () => data.subscription.unsubscribe();
  }, [cargarPerfil]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isLoading,
      isAuthenticated: user !== null,
      emailVerified: user?.email_verified ?? false,
      refresh: cargarPerfil,
      logout,
    }),
    [user, isLoading, cargarPerfil, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
