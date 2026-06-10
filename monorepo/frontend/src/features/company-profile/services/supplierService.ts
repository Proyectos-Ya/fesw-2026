import { apiFetch } from "@/features/shared/api/client";
import type { ProfileData } from "../profileSchema";

/** Proveedor tal como lo devuelve el backend tras crearlo. */
export interface Supplier extends ProfileData {
  id: string;
  user_id: string | null;
  trade_name: string | null;
  created_at: string;
  updated_at: string;
}

/** Crea un proveedor a partir de los datos del wizard de perfil. */
export function createSupplier(data: ProfileData): Promise<Supplier> {
  return apiFetch<Supplier>("/suppliers/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/** Empresa del usuario autenticado; lanza ApiError 404 si aún no crea una. */
export function getMySupplier(): Promise<Supplier> {
  return apiFetch<Supplier>("/suppliers/me");
}
