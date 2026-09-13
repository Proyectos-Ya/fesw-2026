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
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const { user, isAuthenticated } = useAuth();
  const [workspaces, setWorkspaces] = useState<UserWorkspaceSummary[]>([]);
  const [recentIds, setRecentIds] = useState<string[]>([]);
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceContextType | null>(null);
  const [invitations, setInvitations] = useState<SupplierInvitation[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Load recent workspaces for the current user from localStorage
  useEffect(() => {
    if (typeof window === "undefined" || !user?.id) {
      setRecentIds([]);
      return;
    }
    try {
      const stored = localStorage.getItem(`proyectosya_recent_workspaces_${user.id}`);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed)) {
          setRecentIds(parsed.filter((item): item is string => typeof item === "string"));
        }
      }
    } catch {
      setRecentIds([]);
    }
  }, [user?.id]);

  const updateRecentSupplier = useCallback(
    (supplierId: string) => {
      if (!user?.id || !supplierId) return;
      setRecentIds((prev) => {
        const next = [supplierId, ...prev.filter((id) => id !== supplierId)].slice(0, 4);
        try {
          localStorage.setItem(`proyectosya_recent_workspaces_${user.id}`, JSON.stringify(next));
        } catch {
          // ignore storage error
        }
        return next;
      });
    },
    [user?.id],
  );

  useEffect(() => {
    if (activeWorkspace?.active_supplier_id) {
      updateRecentSupplier(activeWorkspace.active_supplier_id);
    }
  }, [activeWorkspace?.active_supplier_id, updateRecentSupplier]);

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
        if (err instanceof ApiError) {
          throw err;
        }
        throw new Error("No se pudo conmutar el espacio de trabajo.");
      }
    },
    [updateRecentSupplier],
  );

  const acceptPendingInvitation = useCallback(
    async (token: string) => {
      await acceptInvitation({ token });
      await Promise.all([refreshInvitations(), refreshWorkspaces()]);
    },
    [refreshInvitations, refreshWorkspaces],
  );

  const recentWorkspaces = useMemo<UserWorkspaceSummary[]>(() => {
    if (workspaces.length === 0) return [];
    const map = new Map(workspaces.map((w) => [w.supplier_id, w]));
    const ordered: UserWorkspaceSummary[] = [];

    // Prioritize active workspace first
    if (activeWorkspace?.active_supplier_id) {
      const active = map.get(activeWorkspace.active_supplier_id);
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
  }, [workspaces, recentIds, activeWorkspace?.active_supplier_id]);

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
};

export function useWorkspace(): WorkspaceContextValue {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) {
    return defaultWorkspaceContextValue;
  }
  return ctx;
}
