/** Parámetro donde viaja el destino al que volver después de iniciar sesión. */
export const RETURN_URL_PARAM = "next";

/**
 * Valida un destino de retorno antes de navegar a él.
 *
 * Solo se aceptan rutas internas. Sin esta comprobación, un enlace como
 * `/login?next=https://sitio-falso.cl` convertiría la propia pantalla de login
 * en un redirector hacia cualquier dominio (open redirect), que es justo lo que
 * usa el phishing para aprovechar la confianza en un dominio conocido.
 *
 * Se rechaza todo lo que no empiece por una sola barra: `//otro.cl` es una URL
 * protocol-relative y lleva fuera igual que `https://otro.cl`, y una barra
 * invertida la normalizan como barra algunos navegadores.
 */
export function sanitizeReturnUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  if (!value.startsWith("/")) return null;
  if (value.startsWith("//") || value.startsWith("/\\")) return null;
  return value;
}

/** Construye la URL de login conservando el destino original. */
export function loginUrlWithReturn(pathname: string, search = ""): string {
  const destino = `${pathname}${search}`;
  if (destino === "/" || destino.startsWith("/login")) return "/login";
  return `/login?${RETURN_URL_PARAM}=${encodeURIComponent(destino)}`;
}
