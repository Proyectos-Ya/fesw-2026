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
import { useAuth } from "@/features/auth/AuthContext";
import {
  acceptInvitation,
  getCurrentWorkspace,
  getMyInvitations,
  listWorkspaces,
  switchWorkspace as switchWorkspaceApi,
} from "./services/workspaceService";
import type {
  SupplierInvitation,
  UserWorkspaceSummary,
  WorkspaceContext as WorkspaceContextType,
} from "./types";

interface WorkspaceContextValue {
  workspaces: UserWorkspaceSummary[];
  activeWorkspace: WorkspaceContextType | null;
  invitations: SupplierInvitation[];
  isLoading: boolean;
  isAdmin: boolean;
  hasPermission: (permission: string) => boolean;
  switchActiveWorkspace: (supplierId: string) => Promise<void>;
  refreshWorkspaces: () => Promise<void>;
  refreshInvitations: () => Promise<void>;
  acceptPendingInvitation: (token: string) => Promise<void>;
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  const [workspaces, setWorkspaces] = useState<UserWorkspaceSummary[]>([]);
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceContextType | null>(null);
  const [invitations, setInvitations] = useState<SupplierInvitation[]>([]);
  const [isLoading, setIsLoading] = useState(true);

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
        if (err instanceof ApiError) {
          throw err;
        }
        throw new Error("No se pudo conmutar el espacio de trabajo.");
      }
    },
    [],
  );

  const acceptPendingInvitation = useCallback(
    async (token: string) => {
      await acceptInvitation({ token });
      await Promise.all([refreshInvitations(), refreshWorkspaces()]);
    },
    [refreshInvitations, refreshWorkspaces],
  );

  useEffect(() => {
    if (isAuthenticated) {
      void refreshWorkspaces();
      void refreshInvitations();
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
      activeWorkspace,
      invitations,
      isLoading,
      isAdmin: activeWorkspace?.is_admin ?? false,
      hasPermission,
      switchActiveWorkspace,
      refreshWorkspaces,
      refreshInvitations,
      acceptPendingInvitation,
    }),
    [
      workspaces,
      activeWorkspace,
      invitations,
      isLoading,
      hasPermission,
      switchActiveWorkspace,
      refreshWorkspaces,
      refreshInvitations,
      acceptPendingInvitation,
    ],
  );

  return (
    <WorkspaceContext.Provider value={value}>
      {children}
    </WorkspaceContext.Provider>
  );
}

const defaultWorkspaceContextValue: WorkspaceContextValue = {
  workspaces: [],
  activeWorkspace: null,
  invitations: [],
  isLoading: false,
  isAdmin: false,
  hasPermission: () => false,
  switchActiveWorkspace: async () => {},
  refreshWorkspaces: async () => {},
  refreshInvitations: async () => {},
  acceptPendingInvitation: async () => {},
};

export function useWorkspace(): WorkspaceContextValue {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) {
    return defaultWorkspaceContextValue;
  }
  return ctx;
}
