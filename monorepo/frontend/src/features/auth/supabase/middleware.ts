import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

import { loginUrlWithReturn } from "../returnUrl";
import { SUPABASE_PUBLISHABLE_KEY, SUPABASE_URL } from "./env";

/** Rutas que se sirven sin sesión. Todo lo demás exige una. */
const PUBLICAS = ["/login", "/register", "/verificar", "/auth", "/privacidad"];

function esPublica(pathname: string): boolean {
  return PUBLICAS.some(
    (ruta) => pathname === ruta || pathname.startsWith(`${ruta}/`),
  );
}

/**
 * Refresca la sesión en cada navegación y bloquea las rutas privadas.
 *
 * El guardia de borde vuelve después de haber estado desactivado (PENDIENTES
 * 3.9). Entonces no podía funcionar: la cookie la emitía el backend en Railway
 * para *su* dominio, así que el borde de Vercel no la veía nunca y devolvía al
 * login a gente que sí tenía sesión. La cookie de Supabase la escribe el
 * cliente **en el propio origen del frontend**, así que acá sí está.
 *
 * Dos detalles que rompen las sesiones en silencio si se tocan:
 *
 * - La respuesta se construye una sola vez y `setAll` escribe sobre ella. Si se
 *   crea un `NextResponse` nuevo después de `getUser()` sin copiarle las
 *   cookies, el token refrescado se pierde y el usuario queda cerrando sesión
 *   sola cada hora.
 * - Se decide con `getUser()`, que revalida contra Supabase, y no mirando si la
 *   cookie existe: una cookie caducada existe igual.
 */
export async function actualizarSesion(peticion: NextRequest) {
  let respuesta = NextResponse.next({ request: peticion });

  const supabase = createServerClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, {
    cookies: {
      getAll() {
        return peticion.cookies.getAll();
      },
      setAll(cookiesAEscribir) {
        cookiesAEscribir.forEach(({ name, value }) =>
          peticion.cookies.set(name, value),
        );
        respuesta = NextResponse.next({ request: peticion });
        cookiesAEscribir.forEach(({ name, value, options }) =>
          respuesta.cookies.set(name, value, options),
        );
      },
    },
  });

  const {
    data: { user },
  } = await supabase.auth.getUser();

  const { pathname, search } = peticion.nextUrl;

  if (!user && !esPublica(pathname)) {
    // Se conserva el destino para volver ahí tras iniciar sesión: es lo que
    // hace que el enlace de un correo de alerta siga llevando a su licitación
    // aunque la sesión se haya caído.
    const destino = new URL(loginUrlWithReturn(pathname, search), peticion.url);
    return NextResponse.redirect(destino);
  }

  return respuesta;
}
