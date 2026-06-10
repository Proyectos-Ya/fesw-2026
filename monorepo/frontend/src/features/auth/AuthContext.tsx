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
import { ApiError } from "@/features/shared/api/client";
import { getMe, logout as logoutRequest } from "./services/authService";
import type { UserPublic } from "./authSchema";

interface AuthContextValue {
  user: UserPublic | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserPublic | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const me = await getMe();
      setUser(me);
    } catch (err) {
      // 401 is the expected "not logged in" path; anything else we still treat as logged-out
      // but surface in dev so it doesn't hide a real bug.
      if (process.env.NODE_ENV !== "production" && !(err instanceof ApiError && err.status === 401)) {
        console.warn("[AuthContext] /auth/me failed:", err);
      }
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await logoutRequest();
    } finally {
      setUser(null);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const me = await getMe();
        if (!cancelled) setUser(me);
      } catch (err) {
        if (
          !cancelled &&
          process.env.NODE_ENV !== "production" &&
          !(err instanceof ApiError && err.status === 401)
        ) {
          console.warn("[AuthContext] /auth/me failed:", err);
        }
        if (!cancelled) setUser(null);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isLoading,
      isAuthenticated: user !== null,
      refresh,
      logout,
    }),
    [user, isLoading, refresh, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
