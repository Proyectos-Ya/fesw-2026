/**
 * Orígenes de la web de Chiripa donde corre el bridge y que la extensión acepta.
 * No usar comodines de hosting compartido (p. ej. *.vercel.app): cualquier tercero
 * podría desplegar ahí una página que hable con la extensión. Si producción vive en
 * un dominio de Vercel, agregar ese host exacto.
 */
export const CHIRIPA_WEB_MATCHES: string[] = ["*://*.chiripa.cl/*", "*://*.proyectosya.cl/*"];

export const DEV_WEB_MATCHES: string[] = ["http://localhost/*", "http://127.0.0.1/*"];

const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1"]);

function parseUrl(value: string): URL | null {
  try {
    return new URL(value);
  } catch {
    return null;
  }
}

/** URL https de mercadopublico.cl o de uno de sus subdominios. */
export function isMercadoPublicoUrl(value: string): boolean {
  const url = parseUrl(value);
  if (!url || url.protocol !== "https:") return false;
  return url.hostname === "mercadopublico.cl" || url.hostname.endsWith(".mercadopublico.cl");
}

/** URL de la API de Chiripa: https, o http solo en localhost. */
export function isAllowedApiUrl(value: string): boolean {
  const url = parseUrl(value);
  if (!url) return false;
  if (url.protocol === "https:") return true;
  return url.protocol === "http:" && LOCAL_HOSTS.has(url.hostname);
}
