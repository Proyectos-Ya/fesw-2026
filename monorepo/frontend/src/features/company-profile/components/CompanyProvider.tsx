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
import {
  getMySupplier,
  uploadMySupplierLogo,
  validateCompanyLogoFile,
  type Supplier,
} from "../services/supplierService";

export type CompanyState =
  | { status: "loading" }
  | { status: "without-company" }
  | { status: "with-company"; supplier: Supplier }
  | { status: "error" };

export interface UploadLogoResult {
  ok: boolean;
  error?: string;
  supplier?: Supplier;
}

export interface CompanyContextValue {
  company: CompanyState;
  /** URL del logo corporativo sincronizado en toda la app desde la nube. */
  logoUrl: string | null;
  /** Sube y persiste el logo corporativo en la nube de forma reactiva. */
  uploadLogo: (file: File) => Promise<UploadLogoResult>;
  /** Actualiza directamente el logo en el estado local de memoria. */
  updateCompanyLogo: (logoUrl: string | null) => void;
  /** Actualiza el estado local tras crear o editar la empresa. */
  setSupplier: (supplier: Supplier) => void;
  /** Vuelve a consultar GET /suppliers/me. */
  refresh: () => Promise<void>;
}

const CompanyContext = createContext<CompanyContextValue | null>(null);

/**
 * Carga la empresa del usuario autenticado y la comparte con
 * toda la app (sidebar, selector de workspaces, página de empresa).
 */
export function CompanyProvider({ children }: { children: React.ReactNode }) {
  const { activeWorkspace, refreshWorkspaces } = useWorkspace();
  const activeSupplierId = activeWorkspace?.active_supplier_id;
  const [company, setCompany] = useState<CompanyState>({ status: "loading" });
  const [logoUrl, setLogoUrl] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const supplier = await getMySupplier();
      setLogoUrl(supplier.logo_url ?? null);
      setCompany({
        status: "with-company",
        supplier,
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
    setLogoUrl(supplier.logo_url ?? null);
    setCompany({
      status: "with-company",
      supplier,
    });
  }, []);

  const uploadLogo = useCallback(
    async (file: File): Promise<UploadLogoResult> => {
      const validationError = validateCompanyLogoFile(file);
      if (validationError) {
        return { ok: false, error: validationError };
      }
      try {
        const updatedSupplier = await uploadMySupplierLogo(file);
        setSupplier(updatedSupplier);
        void refreshWorkspaces();
        return { ok: true, supplier: updatedSupplier };
      } catch (err: unknown) {
        const msg =
          err instanceof Error
            ? err.message
            : "No se pudo subir el logo corporativo.";
        return { ok: false, error: msg };
      }
    },
    [setSupplier, refreshWorkspaces],
  );

  const updateCompanyLogo = useCallback((nextLogoUrl: string | null) => {
    setLogoUrl(nextLogoUrl);
    setCompany((prev) => {
      if (prev.status !== "with-company") return prev;
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
        uploadLogo,
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

/** Acceso opcional a la empresa del usuario; devuelve null si no está dentro de <CompanyProvider>. */
export function useOptionalCompany(): CompanyContextValue | null {
  return useContext(CompanyContext);
}
