/**
 * Identidad de la empresa en sesión en Compra Ágil (CA6). La página consulta
 * /v1/compra-agil/proveedor/empresa/<RUT> con el RUT del proveedor autenticado; se lee
 * solo la URL de esa llamada desde el Resource Timing, sin tokens, cookies ni cuerpos.
 */
const SERVICES_HOST = "servicios-compra-agil.mercadopublico.cl";
const EMPRESA_PATH = /^\/v1\/compra-agil\/proveedor\/empresa\/(\d{1,2}(?:\.?\d{3}){2}-[\dkK])\/?$/;

export function sessionRutFromResourceUrls(urls: string[]): string | null {
  const found = new Set<string>();
  for (const raw of urls) {
    try {
      const url = new URL(raw);
      if (url.hostname !== SERVICES_HOST) continue;
      const match = decodeURIComponent(url.pathname).match(EMPRESA_PATH);
      if (match) found.add(match[1].toUpperCase());
    } catch {
      // URL inválida: se ignora
    }
  }
  return found.size === 1 ? [...found][0] : null;
}

export function resourceUrlsFromPerformance(perf: Performance = performance): string[] {
  return perf.getEntriesByType("resource").map((entry) => entry.name);
}

export async function waitForSessionRut(
  source: () => string[] = () => resourceUrlsFromPerformance(),
  timeoutMs = 10_000,
  intervalMs = 300
): Promise<string | null> {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    const rut = sessionRutFromResourceUrls(source());
    if (rut || Date.now() >= deadline) return rut;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
}
