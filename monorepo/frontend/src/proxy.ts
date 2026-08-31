import { NextResponse } from "next/server";

/**
 * Este guardia dejó de comprobar la sesión a propósito.
 *
 * Comprobaba `request.cookies.has("access_token")`, y eso solo funciona cuando
 * el frontend y el backend comparten dominio. En desarrollo lo comparten —los
 * dos en `localhost`, y las cookies no distinguen puerto— pero en producción el
 * frontend vive en Vercel y el backend en Railway: la cookie la emite el
 * backend para *su* dominio, así que el borde de Vercel no la ve nunca.
 *
 * El efecto era un bucle: el usuario iniciaba sesión, el backend confirmaba con
 * `/auth/me` 200, y este guardia lo devolvía a /login por no encontrar una
 * cookie que jamás iba a estar ahí.
 *
 * Quitarlo no abre ningún hueco de seguridad. Nunca fue un control real —lo
 * decía su propio comentario— sino una conveniencia para evitar el parpadeo de
 * una página protegida. La autorización la aplica el backend en cada petición
 * verificando el JWT, y en el cliente `RequireAuth` cubre los layouts de
 * `(app)` y `(onboarding)`, mostrando un estado de carga mientras resuelve y
 * redirigiendo a /login conservando el destino.
 *
 * Lo que se pierde es cosmético: un instante de estructura de página antes de
 * que el cliente redirija.
 *
 * La solución de fondo es servir la API tras un rewrite de Next para que la
 * cookie vuelva a ser de primera parte (ver PENDIENTES 3.9); con eso este
 * guardia podría recuperarse tal como estaba.
 */
import type { NextRequest } from "next/server";

export default function proxy(_request?: NextRequest) {
  return NextResponse.next();
}

export const config = {
  // Excluye assets estáticos e internos de Next; el resto pasa por el guardia
  matcher: ["/((?!_next|favicon\\.ico|.*\\..*).*)"],
};
