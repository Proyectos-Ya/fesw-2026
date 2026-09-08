import { createBrowserClient } from "@supabase/ssr";

import { SUPABASE_PUBLISHABLE_KEY, SUPABASE_URL } from "./env";

/**
 * Cliente de Supabase para el navegador.
 *
 * `createBrowserClient` devuelve siempre la misma instancia por origen, así que
 * llamarlo en cada componente no abre conexiones de más ni duplica el listener
 * de refresco del token.
 */
export function crearClienteNavegador() {
  return createBrowserClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY);
}
