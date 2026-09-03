import { apiFetch } from "@/features/shared/api/client";
import type { ProfileData } from "../profileSchema";

/** Proveedor tal como lo devuelve el backend tras crearlo. */
export interface Supplier extends Omit<ProfileData, "trade_name"> {
  id: string;
  user_id: string | null;
  trade_name: string | null;
  created_at: string;
  updated_at: string;
}

/** Crea un proveedor a partir de los datos del wizard de perfil. */
export function createSupplier(data: ProfileData): Promise<Supplier> {
  return apiFetch<Supplier>("/suppliers", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/** Empresa del usuario autenticado; lanza ApiError 404 si aún no crea una. */
export function getMySupplier(): Promise<Supplier> {
  return apiFetch<Supplier>("/suppliers/me");
}

/**
 * Empresa del usuario o null si no existe o no se pudo consultar.
 * Permite verificar, tras un timeout o corte de red en la creación,
 * si el backend alcanzó a crear la empresa de todas formas.
 */
export async function getMySupplierOrNull(): Promise<Supplier | null> {
  try {
    return await getMySupplier();
  } catch {
    return null;
  }
}

/** Consulta si ya existe una empresa registrada con ese RUT. */
export async function checkRutExists(rut: string): Promise<boolean> {
  const { exists } = await apiFetch<{ exists: boolean }>(
    `/suppliers/rut-exists?rut=${encodeURIComponent(rut)}`,
  );
  return exists;
}

/** Campos editables de la empresa; el RUT no se puede modificar. */
export type UpdateSupplierData = Partial<Omit<ProfileData, "rut" | "trade_name">> & {
  trade_name?: string | null;
};

/** Edición parcial de la empresa del usuario autenticado. */
export function updateSupplier(data: UpdateSupplierData): Promise<Supplier> {
  return apiFetch<Supplier>("/suppliers/me", {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}
