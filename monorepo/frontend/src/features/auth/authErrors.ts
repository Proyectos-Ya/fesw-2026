/**
 * Traduce los errores de Supabase Auth a algo accionable en español.
 *
 * GoTrue responde en inglés ("User already registered", "Email not
 * confirmed"...) y ese texto llegaba tal cual a los formularios. Se reconoce
 * primero por `code`, que es estable, y si no viene, por el mensaje.
 */
const TRADUCCIONES: { codigos: string[]; patron: RegExp; mensaje: string }[] = [
  {
    codigos: ["user_already_exists", "email_exists"],
    patron: /user already registered/i,
    mensaje: "Ya existe una cuenta con este correo. Inicia sesión o recupera tu contraseña.",
  },
  {
    codigos: ["email_not_confirmed"],
    patron: /email not confirmed/i,
    mensaje:
      "Todavía no confirmas tu correo. Revisa tu bandeja de entrada y abre el enlace que te enviamos.",
  },
  {
    codigos: ["invalid_credentials"],
    patron: /invalid login credentials/i,
    mensaje: "Correo o contraseña incorrectos.",
  },
];

export function mensajeDeErrorAuth(err: unknown, respaldo: string): string {
  if (!(err instanceof Error) || !err.message) return respaldo;

  const codigo = "code" in err && typeof err.code === "string" ? err.code : undefined;
  const traduccion = TRADUCCIONES.find(
    ({ codigos, patron }) =>
      (codigo !== undefined && codigos.includes(codigo)) || patron.test(err.message),
  );
  return traduccion?.mensaje ?? err.message;
}
