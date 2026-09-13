import { apiFetch } from "@/features/shared/api/client";

import type { LoginData, RegisterData, UserPublic } from "../authSchema";
import { crearClienteNavegador } from "../supabase/client";

/** A dónde vuelve el navegador desde Supabase. Se arma con el origin real. */
function urlDeRetorno(ruta: string, destino?: string | null): string {
  const url = new URL(ruta, window.location.origin);
  if (destino) url.searchParams.set("next", destino);
  return url.toString();
}

/**
 * Crea la cuenta en Supabase Auth.
 *
 * Con `enable_confirmations` encendido **no devuelve sesión**: manda el correo
 * de confirmación y el usuario entra recién después de abrir el enlace. Por eso
 * el formulario navega a `/verificar` y no al home.
 */
export async function registrarse(data: RegisterData) {
  const supabase = crearClienteNavegador();
  const { error } = await supabase.auth.signUp({
    email: data.email,
    password: data.password,
    options: {
      emailRedirectTo: urlDeRetorno("/auth/confirm"),
      // Lo que el proveedor sabrá del usuario. El backend lo usa solo para
      // rellenar el nombre del perfil la primera vez; nada de acá decide
      // permisos, porque `user_metadata` lo escribe el propio usuario.
      data: { full_name: data.full_name, phone: data.phone ?? null },
    },
  });
  if (error) throw error;
}

export async function iniciarSesionConCorreo(data: LoginData) {
  const supabase = crearClienteNavegador();
  const { error } = await supabase.auth.signInWithPassword({
    email: data.email,
    password: data.password,
  });
  if (error) throw error;
}

/**
 * Manda al usuario a Google y vuelve por `/auth/callback`.
 *
 * `destino` viaja como `next` en la URL de retorno para no perder a dónde iba;
 * el route handler lo sanea antes de navegar.
 */
export async function iniciarSesionConGoogle(destino?: string | null) {
  const supabase = crearClienteNavegador();
  const { error } = await supabase.auth.signInWithOAuth({
    provider: "google",
    options: { redirectTo: urlDeRetorno("/auth/callback", destino) },
  });
  if (error) throw error;
}

/** Vuelve a mandar el correo de confirmación. */
export async function reenviarConfirmacion(email: string) {
  const supabase = crearClienteNavegador();
  const { error } = await supabase.auth.resend({
    type: "signup",
    email,
    options: { emailRedirectTo: urlDeRetorno("/auth/confirm") },
  });
  if (error) throw error;
}

export async function cerrarSesion(): Promise<void> {
  const supabase = crearClienteNavegador();
  await supabase.auth.signOut();
}

/**
 * El perfil **local**, no el usuario de Supabase.
 *
 * Es la única forma de conocer el `users.id` nuestro, que es al que apuntan
 * todas las claves foráneas del esquema, y es también donde el backend
 * aprovisiona la fila la primera vez que alguien entra.
 */
export async function getMe(): Promise<UserPublic> {
  return apiFetch<UserPublic>("/auth/me");
}
