import { PHASE_PRODUCTION_BUILD } from "next/constants";
import type { NextConfig } from "next";

/**
 * Origen del backend al que Next reenvía las llamadas de API.
 *
 * Es una variable de servidor a propósito (sin `NEXT_PUBLIC_`): el navegador
 * nunca necesita conocer el dominio del backend, y de hecho el objetivo de este
 * rewrite es que no lo conozca.
 */
function resolverBackendOrigin(fase: string): string {
  const declarada = process.env.BACKEND_ORIGIN;
  if (declarada) return declarada;

  // Fuera de desarrollo el build revienta en vez de hornear un destino que no
  // existe. La primera versión de este archivo caía a localhost en silencio y
  // el despliegue salió "verde": Vercel construyó, publicó, y recién en el
  // navegador del usuario aparecía un 404 con
  // `x-vercel-error: DNS_HOSTNAME_RESOLVED_PRIVATE`, porque la plataforma se
  // niega a reenviar a una dirección privada. Un default cómodo convirtió un
  // fallo de configuración en una caída silenciosa de producción.
  // La comprobación va por la fase y no por NODE_ENV: cuando Next evalúa este
  // archivo, NODE_ENV todavía no vale "production" ni siquiera durante
  // `next build`, así que una guarda basada en él no dispara nunca.
  if (fase === PHASE_PRODUCTION_BUILD) {
    throw new Error(
      "BACKEND_ORIGIN no está definida. Es obligatoria fuera de desarrollo: " +
        "sin ella el rewrite de /api apuntaría a http://localhost:8000, que " +
        "desde Vercel no resuelve y devuelve 404 en cada llamada a la API.\n" +
        "Declarala con la URL pública del backend (Railway) en las variables " +
        "de entorno del proyecto, y volvé a desplegar: el destino se resuelve " +
        "en `next build`, así que cambiarla sin reconstruir no surte efecto.",
    );
  }

  return "http://localhost:8000";
}


// Aviso para el despliegue: Next resuelve los rewrites en `next build` y los
// hornea en `routes-manifest.json`, no los lee en cada arranque. La variable
// tiene que estar presente **en el build**; cambiarla en el panel de Vercel no
// surte efecto hasta el siguiente despliegue. Comprobado levantando `next start`
// con otro valor: seguía reenviando al destino del build anterior.

const construirConfig = (fase: string): NextConfig => ({
  /**
   * La API se sirve bajo `/api` del propio dominio del frontend y Next la
   * reenvía al backend por detrás.
   *
   * El motivo es la cookie de sesión. El frontend vive en Vercel y el backend
   * en Railway: si el navegador llama a Railway directamente, la cookie que ese
   * dominio emite es de *tercera parte*. Con `SameSite=Lax` —el valor por
   * defecto— el navegador la guarda pero no la reenvía, y con `SameSite=None`
   * la descartan igual los navegadores que bloquean cookies de terceros
   * (Safari y Brave de fábrica). El síntoma en producción era un bucle:
   * `POST /auth/login` respondía 200 y el `GET /auth/me` siguiente 401, así que
   * el usuario volvía al login una y otra vez.
   *
   * Con el rewrite el navegador habla solo con el dominio de Vercel, la cookie
   * es de primera parte y el problema desaparece en todos los navegadores. De
   * paso, `CORS_ORIGINS` deja de ser necesario y las URLs de preview de Vercel
   * —que cambian en cada despliegue y nunca iban a estar en esa lista—
   * funcionan solas.
   *
   * El costo es un salto de red extra: el tráfico de API pasa por Vercel.
   */
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${resolverBackendOrigin(fase)}/:path*`,
      },
    ];
  },
});

export default (fase: string) => construirConfig(fase);
