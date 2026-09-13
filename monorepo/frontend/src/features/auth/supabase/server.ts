import { cookies } from "next/headers";
import { createServerClient } from "@supabase/ssr";

import { SUPABASE_PUBLISHABLE_KEY, SUPABASE_URL } from "./env";

/**
 * Cliente de Supabase para Server Components y Route Handlers.
 *
 * Se construye uno por petición y no se cachea: lleva dentro las cookies de esa
 * petición, y compartirlo entre peticiones sería compartir sesiones.
 */
export async function crearClienteServidor() {
  const almacen = await cookies();

  return createServerClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, {
    cookies: {
      getAll() {
        return almacen.getAll();
      },
      setAll(cookiesAEscribir) {
        try {
          cookiesAEscribir.forEach(({ name, value, options }) =>
            almacen.set(name, value, options),
          );
        } catch {
          // Un Server Component no puede escribir cookies: Next lo prohíbe
          // porque la respuesta ya empezó a transmitirse. No es un error, es el
          // caso normal: el refresco del token lo hace el middleware, que sí
          // puede, y acá solo se lee.
        }
      },
    },
  });
}
