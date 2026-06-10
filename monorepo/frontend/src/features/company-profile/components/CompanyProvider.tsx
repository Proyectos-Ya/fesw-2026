"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { ApiError } from "@/features/shared/api/client";
import { getMySupplier, type Supplier } from "../services/supplierService";

export type CompanyState =
  | { status: "loading" }
  | { status: "without-company" }
  | { status: "with-company"; supplier: Supplier }
  | { status: "error" };

interface CompanyContextValue {
  company: CompanyState;
  /** Actualiza el estado local tras crear o editar la empresa. */
  setSupplier: (supplier: Supplier) => void;
  /** Vuelve a consultar GET /suppliers/me. */
  refresh: () => Promise<void>;
}

const CompanyContext = createContext<CompanyContextValue | null>(null);

/**
 * Carga la empresa del usuario autenticado una sola vez y la comparte con
 * toda la app (sidebar, home, página de empresa).
 */
export function CompanyProvider({ children }: { children: React.ReactNode }) {
  const [company, setCompany] = useState<CompanyState>({ status: "loading" });

  const refresh = useCallback(async () => {
    try {
      const supplier = await getMySupplier();
      setCompany({ status: "with-company", supplier });
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 404) {
        setCompany({ status: "without-company" });
      } else {
        setCompany({ status: "error" });
      }
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const setSupplier = useCallback((supplier: Supplier) => {
    setCompany({ status: "with-company", supplier });
  }, []);

  return (
    <CompanyContext.Provider value={{ company, setSupplier, refresh }}>
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
