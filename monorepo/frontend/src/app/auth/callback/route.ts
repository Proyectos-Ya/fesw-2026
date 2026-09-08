import { NextResponse, type NextRequest } from "next/server";

import { sanitizeReturnUrl } from "@/features/auth/returnUrl";
import { crearClienteServidor } from "@/features/auth/supabase/server";

/**
 * Vuelta desde un proveedor externo (hoy, Google).
 *
 * Supabase manda acá con un `code` de un solo uso que hay que canjear por la
 * sesión; el canje escribe las cookies, por eso es un route handler y no una
 * página.
 *
 * El destino pasa por `sanitizeReturnUrl`. Un callback de OAuth es un blanco
 * mejor para un open redirect que el propio formulario de login: la URL la arma
 * el proveedor, el usuario la ve venir de un dominio en el que confía, y el
 * parámetro viaja intacto.
 */
export async function GET(peticion: NextRequest) {
  const { searchParams, origin } = new URL(peticion.url);
  const destino = sanitizeReturnUrl(searchParams.get("next")) ?? "/";

  // Google devuelve el rechazo acá mismo (`error=access_denied` cuando alguien
  // cancela en la pantalla de consentimiento). Sin esta rama se vería el error
  // genérico de "código faltante", que apunta a otro lado.
  const error = searchParams.get("error_description") ?? searchParams.get("error");
  if (error) {
    return NextResponse.redirect(
      new URL(`/login?error=${encodeURIComponent(error)}`, origin),
    );
  }

  const code = searchParams.get("code");
  if (!code) {
    return NextResponse.redirect(new URL("/login?error=sin_codigo", origin));
  }

  const supabase = await crearClienteServidor();
  const { error: fallo } = await supabase.auth.exchangeCodeForSession(code);
  if (fallo) {
    return NextResponse.redirect(
      new URL(`/login?error=${encodeURIComponent(fallo.message)}`, origin),
    );
  }

  return NextResponse.redirect(new URL(destino, origin));
}
