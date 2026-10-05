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
import {
  ApiError,
  registrarManejadorRevocacionAcceso,
} from "@/features/shared/api/client";
import { Button } from "@/features/shared/components/Button";
import { Icon } from "@/features/shared/components/Icon";
import { useAuth } from "@/features/auth/AuthContext";
import {
  acceptInvitation,
  clearActiveWorkspace,
  getCurrentWorkspace,
  getMyInvitations,
  listWorkspaces,
  rejectInvitation,
  switchWorkspace as switchWorkspaceApi,
} from "./services/workspaceService";
import type {
  SupplierInvitation,
  UserWorkspaceSummary,
  WorkspaceContext as WorkspaceContextType,
} from "./types";

function isRevokedAccessError(
  err: unknown,
): err is { status: number; message: string } {
  if (err instanceof ApiError) {
    return err.status === 403 && err.message.toLowerCase().includes("revocado");
  }
  if (
    err &&
    typeof err === "object" &&
    "status" in err &&
    "message" in err &&
    (err as { status: unknown }).status === 403 &&
    typeof (err as { message: unknown }).message === "string"
  ) {
    return (err as { message: string }).message
      .toLowerCase()
      .includes("revocado");
  }
  return false;
}

interface WorkspaceContextValue {
  workspaces: UserWorkspaceSummary[];
  recentWorkspaces: UserWorkspaceSummary[];
  activeWorkspace: WorkspaceContextType | null;
  invitations: SupplierInvitation[];
  isLoading: boolean;
  isAdmin: boolean;
  hasPermission: (permission: string) => boolean;
  switchActiveWorkspace: (supplierId: string) => Promise<void>;
  refreshWorkspaces: () => Promise<void>;
  refreshInvitations: () => Promise<void>;
  acceptPendingInvitation: (token: string) => Promise<void>;
  rejectPendingInvitation: (token: string) => Promise<void>;
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const { user, isAuthenticated } = useAuth();
  const [workspaces, setWorkspaces] = useState<UserWorkspaceSummary[]>([]);
  const [recentIds, setRecentIds] = useState<string[]>([]);
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceContextType | null>(null);
  const [invitations, setInvitations] = useState<SupplierInvitation[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [revokedMessage, setRevokedMessage] = useState<string | null>(null);
  const [isClearingRevoked, setIsClearingRevoked] = useState(false);

  const currentUserId = user?.id;

  useEffect(() => {
    registrarManejadorRevocacionAcceso((mensaje) => {
      setRevokedMessage(mensaje);
    });
    return () => {
      registrarManejadorRevocacionAcceso(null);
    };
  }, []);

  // Load recent workspaces for the current user from localStorage
  useEffect(() => {
    if (typeof window === "undefined" || !currentUserId) {
      setRecentIds([]);
      return;
    }
    try {
      const stored = localStorage.getItem(`proyectosya_recent_workspaces_${currentUserId}`);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed)) {
          setRecentIds(parsed.filter((item): item is string => typeof item === "string"));
        }
      }
    } catch {
      setRecentIds([]);
    }
  }, [currentUserId]);

  const updateRecentSupplier = useCallback(
    (supplierId: string) => {
      if (!currentUserId || !supplierId) return;
      setRecentIds((prev) => {
        const next = [supplierId, ...prev.filter((id) => id !== supplierId)].slice(0, 4);
        try {
          localStorage.setItem(`proyectosya_recent_workspaces_${currentUserId}`, JSON.stringify(next));
        } catch {
          // ignore storage error
        }
        return next;
      });
    },
    [currentUserId],
  );

  const activeSupplierId = activeWorkspace?.active_supplier_id;
  useEffect(() => {
    if (activeSupplierId) {
      updateRecentSupplier(activeSupplierId);
    }
  }, [activeSupplierId, updateRecentSupplier]);

  const refreshInvitations = useCallback(async () => {
    if (!isAuthenticated) {
      setInvitations([]);
      return;
    }
    try {
      const pending = await getMyInvitations();
      setInvitations(pending);
    } catch (err) {
      if (process.env.NODE_ENV !== "production") {
        console.warn("[WorkspaceContext] Error fetching invitations:", err);
      }
    }
  }, [isAuthenticated]);

  const refreshWorkspaces = useCallback(async () => {
    if (!isAuthenticated) {
      setWorkspaces([]);
      setActiveWorkspace(null);
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    try {
      const [list, current] = await Promise.allSettled([
        listWorkspaces(),
        getCurrentWorkspace(),
      ]);

      if (list.status === "fulfilled") {
        setWorkspaces(list.value);
      }
      if (current.status === "fulfilled") {
        setActiveWorkspace(current.value);
      } else {
        if (isRevokedAccessError(current.reason)) {
          setRevokedMessage(current.reason.message);
        }
        setActiveWorkspace(null);
      }
    } catch (err) {
      if (process.env.NODE_ENV !== "production") {
        console.warn("[WorkspaceContext] Error fetching workspaces:", err);
      }
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated]);

  const switchActiveWorkspace = useCallback(
    async (supplierId: string) => {
      try {
        updateRecentSupplier(supplierId);
        const newContext = await switchWorkspaceApi({ supplier_id: supplierId });
        setActiveWorkspace(newContext);
        setWorkspaces((prev) =>
          prev.map((w) => ({
            ...w,
            is_active_context: w.supplier_id === supplierId,
          })),
        );
        if (typeof window !== "undefined" && window.location.pathname === "/workspaces") {
          window.location.href = "/";
        } else if (typeof window !== "undefined") {
          window.location.reload();
        }
      } catch (err) {
        if (isRevokedAccessError(err)) {
          setRevokedMessage(err.message);
        }
        if (err instanceof ApiError) {
          throw err;
        }
        throw new Error("No se pudo conmutar el espacio de trabajo.");
      }
    },
    [updateRecentSupplier],
  );

  const handleReturnHomeAfterRevocation = useCallback(async () => {
    setIsClearingRevoked(true);
    try {
      await clearActiveWorkspace();
    } catch {
      // Continúa el restablecimiento local aunque falle la llamada
    } finally {
      setRevokedMessage(null);
      setActiveWorkspace(null);
      setIsClearingRevoked(false);
      await refreshWorkspaces();
      if (typeof window !== "undefined" && window.location.pathname !== "/") {
        window.location.href = "/";
      }
    }
  }, [refreshWorkspaces]);

  const acceptPendingInvitation = useCallback(
    async (token: string) => {
      await acceptInvitation({ token });
      await Promise.all([refreshInvitations(), refreshWorkspaces()]);
    },
    [refreshInvitations, refreshWorkspaces],
  );

  const rejectPendingInvitation = useCallback(
    async (token: string) => {
      await rejectInvitation({ token });
      await refreshInvitations();
    },
    [refreshInvitations],
  );

  const recentWorkspaces = useMemo<UserWorkspaceSummary[]>(() => {
    if (workspaces.length === 0) return [];
    const map = new Map(workspaces.map((w) => [w.supplier_id, w]));
    const ordered: UserWorkspaceSummary[] = [];

    // Prioritize active workspace first
    if (activeSupplierId) {
      const active = map.get(activeSupplierId);
      if (active) {
        ordered.push(active);
      }
    }

    // Add according to recentIds
    for (const id of recentIds) {
      if (ordered.length >= 4) break;
      const found = map.get(id);
      if (found && !ordered.some((w) => w.supplier_id === id)) {
        ordered.push(found);
      }
    }

    // Fill up to 4 with other workspaces if available
    for (const w of workspaces) {
      if (ordered.length >= 4) break;
      if (!ordered.some((item) => item.supplier_id === w.supplier_id)) {
        ordered.push(w);
      }
    }

    return ordered.slice(0, 4);
  }, [workspaces, recentIds, activeSupplierId]);

  useEffect(() => {
    if (isAuthenticated) {
      void refreshWorkspaces();
      void refreshInvitations();

      const handleFocus = () => {
        void refreshInvitations();
      };

      if (typeof window !== "undefined") {
        window.addEventListener("focus", handleFocus);
      }
      const timer = setInterval(() => {
        void refreshInvitations();
      }, 60_000);

      return () => {
        if (typeof window !== "undefined") {
          window.removeEventListener("focus", handleFocus);
        }
        clearInterval(timer);
      };
    } else {
      setWorkspaces([]);
      setActiveWorkspace(null);
      setInvitations([]);
      setIsLoading(false);
    }
  }, [isAuthenticated, refreshWorkspaces, refreshInvitations]);

  const hasPermission = useCallback(
    (permission: string): boolean => {
      if (!activeWorkspace) return false;
      if (activeWorkspace.is_admin) return true;
      return activeWorkspace.permissions.includes(permission);
    },
    [activeWorkspace],
  );

  const value = useMemo<WorkspaceContextValue>(
    () => ({
      workspaces,
      recentWorkspaces,
      activeWorkspace,
      invitations,
      isLoading,
      isAdmin: activeWorkspace?.is_admin ?? false,
      hasPermission,
      switchActiveWorkspace,
      refreshWorkspaces,
      refreshInvitations,
      acceptPendingInvitation,
      rejectPendingInvitation,
    }),
    [
      workspaces,
      recentWorkspaces,
      activeWorkspace,
      invitations,
      isLoading,
      hasPermission,
      switchActiveWorkspace,
      refreshWorkspaces,
      refreshInvitations,
      acceptPendingInvitation,
      rejectPendingInvitation,
    ],
  );

  return (
    <WorkspaceContext.Provider value={value}>
      {children}
      {revokedMessage && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="revoked-workspace-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs"
        >
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl border border-border-subtle">
            <div className="flex items-center gap-3 text-danger">
              <Icon name="shield-alert" size={22} />
              <h2
                id="revoked-workspace-title"
                className="text-lg font-bold text-text-strong"
              >
                Acceso restringido
              </h2>
            </div>
            <p className="mt-3 text-sm text-text-muted leading-relaxed">
              {revokedMessage} Un administrador de la empresa revocó tus
              permisos sobre este espacio de trabajo.
            </p>
            <div className="mt-6 flex justify-end">
              <Button
                type="button"
                variant="primary"
                isLoading={isClearingRevoked}
                onClick={() => void handleReturnHomeAfterRevocation()}
                className="font-bold"
              >
                Ir al inicio
              </Button>
            </div>
          </div>
        </div>
      )}
    </WorkspaceContext.Provider>
  );
}

const defaultWorkspaceContextValue: WorkspaceContextValue = {
  workspaces: [],
  recentWorkspaces: [],
  activeWorkspace: null,
  invitations: [],
  isLoading: false,
  isAdmin: false,
  hasPermission: () => false,
  switchActiveWorkspace: async () => {},
  refreshWorkspaces: async () => {},
  refreshInvitations: async () => {},
  acceptPendingInvitation: async () => {},
  rejectPendingInvitation: async () => {},
};

export function useWorkspace(): WorkspaceContextValue {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) {
    return defaultWorkspaceContextValue;
  }
  return ctx;
}
