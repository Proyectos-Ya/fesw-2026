"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { ApiError } from "@/features/shared/api/client";
import { useWorkspace } from "@/features/workspaces/WorkspaceContext";
import { getMySupplier, type Supplier } from "../services/supplierService";

export type CompanyState =
  | { status: "loading" }
  | { status: "without-company" }
  | { status: "with-company"; supplier: Supplier }
  | { status: "error" };

export interface CompanyContextValue {
  company: CompanyState;
  /** URL (o Data URL) del logo corporativo sincronizado en toda la app. */
  logoUrl: string | null;
  /** Actualiza y persiste el logo corporativo de forma reactiva. */
  updateCompanyLogo: (logoUrl: string | null) => void;
  /** Actualiza el estado local tras crear o editar la empresa. */
  setSupplier: (supplier: Supplier) => void;
  /** Vuelve a consultar GET /suppliers/me. */
  refresh: () => Promise<void>;
}

const CompanyContext = createContext<CompanyContextValue | null>(null);

export function getCompanyLogoStorageKey(supplierId: string): string {
  return `chiripa_company_logo_${supplierId}`;
}

function readStoredCompanyLogo(supplierId: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(getCompanyLogoStorageKey(supplierId));
  } catch {
    return null;
  }
}

function writeStoredCompanyLogo(supplierId: string, logoUrl: string | null) {
  if (typeof window === "undefined") return;
  try {
    const key = getCompanyLogoStorageKey(supplierId);
    if (logoUrl) {
      window.localStorage.setItem(key, logoUrl);
    } else {
      window.localStorage.removeItem(key);
    }
  } catch {
    // Ignore storage quota or access errors
  }
}

/**
 * Carga la empresa del usuario autenticado una sola vez y la comparte con
 * toda la app (sidebar, home, página de empresa).
 */
export function CompanyProvider({ children }: { children: React.ReactNode }) {
  const { activeWorkspace } = useWorkspace();
  const activeSupplierId = activeWorkspace?.active_supplier_id;
  const [company, setCompany] = useState<CompanyState>({ status: "loading" });
  const [logoUrl, setLogoUrl] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const supplier = await getMySupplier();
      const storedLogo =
        readStoredCompanyLogo(supplier.id) ?? supplier.logo_url ?? null;
      setLogoUrl(storedLogo);
      setCompany({
        status: "with-company",
        supplier: { ...supplier, logo_url: storedLogo },
      });
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 404) {
        setLogoUrl(null);
        setCompany({ status: "without-company" });
      } else {
        setCompany({ status: "error" });
      }
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh, activeSupplierId]);

  const setSupplier = useCallback((supplier: Supplier) => {
    const resolvedLogo =
      supplier.logo_url ?? readStoredCompanyLogo(supplier.id) ?? null;
    setLogoUrl(resolvedLogo);
    setCompany({
      status: "with-company",
      supplier: { ...supplier, logo_url: resolvedLogo },
    });
  }, []);

  const updateCompanyLogo = useCallback((nextLogoUrl: string | null) => {
    setLogoUrl(nextLogoUrl);
    setCompany((prev) => {
      if (prev.status !== "with-company") return prev;
      writeStoredCompanyLogo(prev.supplier.id, nextLogoUrl);
      return {
        status: "with-company",
        supplier: {
          ...prev.supplier,
          logo_url: nextLogoUrl,
        },
      };
    });
  }, []);

  return (
    <CompanyContext.Provider
      value={{
        company,
        logoUrl,
        updateCompanyLogo,
        setSupplier,
        refresh,
      }}
    >
      {children}
    </CompanyContext.Provider>
  );
}

/** Acceso a la empresa del usuario; debe usarse dentro de <CompanyProvider>. */
export function useCompany(): CompanyContextValue {
  const context = useContext(CompanyContext);
  if (!context) {
    throw new Error("useCompany debe usarse dentro de <CompanyProvider>");
  }
  return context;
}

/** Acceso opcional al contexto de empresa para componentes reutilizados fuera del provider. */
export function useOptionalCompany(): CompanyContextValue | null {
  return useContext(CompanyContext);
}
