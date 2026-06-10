import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/** Nombre de la cookie httpOnly que deja el backend al iniciar sesión. */
const AUTH_COOKIE = "access_token";

/** Rutas accesibles sin sesión iniciada. */
const PUBLIC_PATHS = ["/login", "/register"];

/**
 * Guardia de autenticación a nivel de borde:
 * - Sin cookie de sesión, toda ruta de la app redirige a /login.
 * - Con cookie, /login y /register redirigen al home.
 * La validez real del token la verifica el backend en cada request.
 */
export default function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSession = request.cookies.has(AUTH_COOKIE);
  const isPublicPath = PUBLIC_PATHS.some((path) => pathname.startsWith(path));

  if (!hasSession && !isPublicPath) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  if (hasSession && isPublicPath) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  return NextResponse.next();
}

export const config = {
  // Excluye assets estáticos e internos de Next; el resto pasa por el guardia
  matcher: ["/((?!_next|favicon\\.ico|.*\\..*).*)"],
};
