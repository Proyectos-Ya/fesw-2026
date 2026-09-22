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

/**
 * Esperas entre consultas de `waitForMySupplier`: una consulta inmediata y una
 * tras cada espera, ~15 s en total. Cubre de sobra el margen entre el corte del
 * cliente y el commit del backend, que tiene su propio tope por debajo de 60 s.
 */
const WAIT_FOR_SUPPLIER_DELAYS_MS = [1000, 2000, 4000, 8000];

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Consulta la empresa del usuario hasta que aparezca o se agoten las esperas.
 *
 * Una sola consulta tras un timeout pierde la carrera contra el backend, que
 * sigue trabajando después de que el navegador corta: el 3-sep devolvió 404 y
 * la empresa se confirmó dos segundos más tarde.
 */
export async function waitForMySupplier({
  delaysMs = WAIT_FOR_SUPPLIER_DELAYS_MS,
}: { delaysMs?: readonly number[] } = {}): Promise<Supplier | null> {
  const first = await getMySupplierOrNull();
  if (first) return first;

  for (const delay of delaysMs) {
    await sleep(delay);
    const supplier = await getMySupplierOrNull();
    if (supplier) return supplier;
  }
  return null;
}

/** Consulta si ya existe una empresa registrada con ese RUT. */
export async function checkRutExists(rut: string): Promise<boolean> {
  const { exists } = await apiFetch<{ exists: boolean }>(
    `/suppliers/rut-exists?rut=${encodeURIComponent(rut)}`,
  );
  return exists;
}

/**
 * Borrador de perfil sugerido a partir del RUT, con las actividades económicas
 * del SII (vía SRE o Web Empresario, según la configuración del backend). No se
 * guarda nada: el usuario lo revisa en el wizard antes de crear la empresa.
 */
export interface CompanyProfileImport {
  source: string;
  rut: string;
  legal_name: string;
  is_active: boolean | null;
  /** Nombres de región del wizard; vacío si la fuente no entrega domicilio. */
  regions: string[];
  sectors: string[];
  keywords: string[];
  /** Avisos sobre lo que no se pudo deducir. */
  notices: string[];
}

/** Importa los datos de la empresa desde su RUT. */
export function importCompanyProfile(rut: string): Promise<CompanyProfileImport> {
  return apiFetch<CompanyProfileImport>(
    `/suppliers/profile-import?rut=${encodeURIComponent(rut)}`,
  );
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
