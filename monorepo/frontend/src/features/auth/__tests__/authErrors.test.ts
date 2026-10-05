import { describe, expect, it } from "vitest";
import { correoSinConfirmar, mensajeDeErrorAuth } from "../authErrors";

/** Imita el AuthError de supabase-js: un Error con `code` opcional. */
function authError(message: string, code?: string): Error {
  return Object.assign(new Error(message), code ? { code } : {});
}

const RESPALDO = "Ocurrió un error inesperado. Inténtalo de nuevo.";

describe("mensajeDeErrorAuth", () => {
  it("traduce el correo ya registrado por su código", () => {
    expect(
      mensajeDeErrorAuth(authError("User already registered", "user_already_exists"), RESPALDO),
    ).toBe("Ya existe una cuenta con este correo. Inicia sesión o recupera tu contraseña.");
  });

  it("traduce el correo ya registrado aunque no venga el código", () => {
    expect(mensajeDeErrorAuth(authError("User already registered"), RESPALDO)).toBe(
      "Ya existe una cuenta con este correo. Inicia sesión o recupera tu contraseña.",
    );
  });

  it("traduce el correo sin confirmar", () => {
    expect(mensajeDeErrorAuth(authError("Email not confirmed"), RESPALDO)).toBe(
      "Todavía no confirmas tu correo. Revisa tu bandeja de entrada y abre el enlace que te enviamos.",
    );
  });

  it("traduce las credenciales inválidas", () => {
    expect(mensajeDeErrorAuth(authError("Invalid login credentials"), RESPALDO)).toBe(
      "Correo o contraseña incorrectos.",
    );
  });

  it("usa el mensaje de respaldo si el error no es un Error", () => {
    expect(mensajeDeErrorAuth("algo raro", RESPALDO)).toBe(RESPALDO);
  });

  it("usa el mensaje de respaldo si el Error viene vacío", () => {
    expect(mensajeDeErrorAuth(new Error(""), RESPALDO)).toBe(RESPALDO);
  });

  it("deja pasar un mensaje que no conoce", () => {
    expect(mensajeDeErrorAuth(authError("Algo nuevo"), RESPALDO)).toBe("Algo nuevo");
  });
});

describe("correoSinConfirmar", () => {
  it("reconoce el error por su código", () => {
    expect(correoSinConfirmar(authError("x", "email_not_confirmed"))).toBe(true);
  });

  it("reconoce el error por su mensaje", () => {
    expect(correoSinConfirmar(authError("Email not confirmed"))).toBe(true);
  });

  it("no confunde otros errores", () => {
    expect(correoSinConfirmar(authError("Invalid login credentials", "invalid_credentials"))).toBe(false);
    expect(correoSinConfirmar("texto")).toBe(false);
  });
});
