import type { EmailOtpType } from "@supabase/supabase-js";
import { NextResponse, type NextRequest } from "next/server";

import { sanitizeReturnUrl } from "@/features/auth/returnUrl";
import { crearClienteServidor } from "@/features/auth/supabase/server";

/**
 * Destino del enlace del correo de confirmación.
 *
 * Funciona con `token_hash`, y eso depende de la plantilla propia
 * (`supabase/templates/confirm.html`): la de fábrica usa
 * `{{ .ConfirmationURL }}`, que apunta a `/auth/v1/verify` y consume el token
 * del lado de Supabase antes de redirigir, así que acá nunca llegaría nada que
 * canjear. Si alguien vuelve a la plantilla por defecto, el síntoma es este
 * endpoint respondiendo siempre "enlace inválido".
 *
 * `verifyOtp` devuelve una sesión ya confirmada, así que el usuario entra
 * directo sin volver a escribir su contraseña.
 */
export async function GET(peticion: NextRequest) {
  const { searchParams, origin } = new URL(peticion.url);
  const destino = sanitizeReturnUrl(searchParams.get("next")) ?? "/";

  const token_hash = searchParams.get("token_hash");
  const type = searchParams.get("type") as EmailOtpType | null;

  if (!token_hash || !type) {
    return NextResponse.redirect(new URL("/login?error=enlace_invalido", origin));
  }

  const supabase = await crearClienteServidor();
  const { error } = await supabase.auth.verifyOtp({ type, token_hash });
  if (error) {
    // El caso habitual es un enlace vencido (una hora) o ya usado. Se manda a
    // /verificar y no a /login porque ahí está el botón de reenviar, que es lo
    // único que resuelve la situación.
    return NextResponse.redirect(
      new URL(`/verificar?error=${encodeURIComponent(error.message)}`, origin),
    );
  }

  return NextResponse.redirect(new URL(destino, origin));
}
