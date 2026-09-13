/**
 * Las dos variables públicas de Supabase, comprobadas al importar.
 *
 * Van con `NEXT_PUBLIC_` a propósito, y es la excepción a la regla que fija
 * `next.config.ts` de que el navegador no conozca el backend: la clave
 * publicable está diseñada para viajar al cliente, y sin la URL no hay forma de
 * hablar con Supabase desde el navegador. El backend real sigue detrás del
 * rewrite de `/api`.
 *
 * Se lanza en vez de caer a un valor por defecto: un default cómodo convierte un
 * fallo de configuración en un despliegue "verde" donde nadie puede entrar y el
 * único síntoma es un error en la consola del navegador de otra persona.
 * `next.config.ts` documenta el mismo criterio y la misma cicatriz.
 */
function exigir(nombre: string, valor: string | undefined): string {
  if (!valor) {
    throw new Error(
      `${nombre} no está definida. Es obligatoria: sin ella el navegador no ` +
        "puede hablar con Supabase Auth y nadie puede iniciar sesión.\n" +
        "En local sale de `supabase status`; en Vercel se declara en las " +
        "variables del proyecto y hay que **volver a desplegar**, porque Next " +
        "hornea las NEXT_PUBLIC_ en el build.",
    );
  }
  return valor;
}

export const SUPABASE_URL = exigir(
  "NEXT_PUBLIC_SUPABASE_URL",
  process.env.NEXT_PUBLIC_SUPABASE_URL,
);

export const SUPABASE_PUBLISHABLE_KEY = exigir(
  "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
);
