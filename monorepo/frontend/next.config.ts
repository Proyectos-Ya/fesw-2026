import type { NextConfig } from "next";

/**
 * Origen del backend al que Next reenvía las llamadas de API.
 *
 * Es una variable de servidor a propósito (sin `NEXT_PUBLIC_`): el navegador
 * nunca necesita conocer el dominio del backend, y de hecho el objetivo de este
 * rewrite es que no lo conozca.
 */
const BACKEND_ORIGIN = process.env.BACKEND_ORIGIN ?? "http://localhost:8000";

// Aviso para el despliegue: Next resuelve los rewrites en `next build` y los
// hornea en `routes-manifest.json`, no los lee en cada arranque. La variable
// tiene que estar presente **en el build**; cambiarla en el panel de Vercel no
// surte efecto hasta el siguiente despliegue. Comprobado levantando `next start`
// con otro valor: seguía reenviando al destino del build anterior.

const nextConfig: NextConfig = {
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
        destination: `${BACKEND_ORIGIN}/:path*`,
      },
    ];
  },
};

export default nextConfig;
