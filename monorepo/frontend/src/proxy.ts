import type { NextRequest } from "next/server";

import { actualizarSesion } from "@/features/auth/supabase/middleware";

/**
 * Refresco de sesión y guardia de borde.
 *
 * El guardia estuvo desactivado a propósito durante un tiempo (PENDIENTES 3.9),
 * y con razón: comprobaba `request.cookies.has("access_token")`, una cookie que
 * emitía el backend en Railway para su propio dominio. En desarrollo funcionaba
 * —frontend y backend compartían `localhost`, y las cookies no distinguen
 * puerto— pero en producción el borde de Vercel no la veía nunca, así que
 * devolvía al login a gente que acababa de iniciar sesión.
 *
 * Con Supabase Auth la cookie de sesión la escribe el cliente en el **origen
 * del propio frontend**, en Vercel igual que en local, así que el guardia
 * vuelve a tener algo que mirar. Además hay que pasar por acá sí o sí: es el
 * único lugar que puede escribir la cookie con el token refrescado.
 *
 * `RequireAuth` sigue en el cliente y no sobra: el borde sabe si hay sesión de
 * Supabase, pero no si el perfil local de `/auth/me` resolvió.
 */
export default async function proxy(request: NextRequest) {
  return actualizarSesion(request);
}

export const config = {
  // Se excluyen los internos de Next, los archivos con extensión y `/api`.
  // Excluir `/api` importa: si no, cada llamada del cliente pagaría una
  // revalidación contra Supabase antes de llegar al rewrite hacia el backend,
  // que ya verifica el token por su cuenta.
  matcher: ["/((?!_next|api|favicon\\.ico|.*\\..*).*)"],
};
