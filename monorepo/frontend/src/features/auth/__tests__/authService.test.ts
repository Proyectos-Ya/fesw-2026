/**
 * Lo que el servicio le pide a Supabase.
 *
 * Importa sobre todo a dónde se le dice que vuelva: un `redirectTo` con un
 * destino externo convierte el ingreso con Google en un redirector hacia
 * cualquier dominio.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

const signUp = vi.fn().mockResolvedValue({ error: null });
const signInWithPassword = vi.fn().mockResolvedValue({ error: null });
const signInWithOAuth = vi.fn().mockResolvedValue({ error: null });
const resend = vi.fn().mockResolvedValue({ error: null });

vi.mock("../supabase/client", () => ({
  crearClienteNavegador: () => ({
    auth: { signUp, signInWithPassword, signInWithOAuth, resend },
  }),
}));

import {
  iniciarSesionConGoogle,
  registrarse,
  reenviarConfirmacion,
} from "../services/authService";

beforeEach(() => {
  vi.clearAllMocks();
});

describe("registrarse", () => {
  it("pide que el correo de confirmación vuelva a /auth/confirm", async () => {
    await registrarse({
      email: "ana@ejemplo.cl",
      password: "supersecreta",
      full_name: "Ana Díaz",
    });

    expect(signUp.mock.calls[0][0].options.emailRedirectTo).toBe(
      "http://localhost:3000/auth/confirm",
    );
  });

  it("manda el nombre para que el perfil local nazca con él", async () => {
    await registrarse({
      email: "ana@ejemplo.cl",
      password: "supersecreta",
      full_name: "Ana Díaz",
    });

    expect(signUp.mock.calls[0][0].options.data.full_name).toBe("Ana Díaz");
  });
});

describe("iniciarSesionConGoogle", () => {
  it("vuelve a /auth/callback del propio origen", async () => {
    await iniciarSesionConGoogle();

    expect(signInWithOAuth.mock.calls[0][0]).toMatchObject({ provider: "google" });
    expect(signInWithOAuth.mock.calls[0][0].options.redirectTo).toBe(
      "http://localhost:3000/auth/callback",
    );
  });

  it("conserva el destino como parámetro next", async () => {
    await iniciarSesionConGoogle("/matches");

    expect(signInWithOAuth.mock.calls[0][0].options.redirectTo).toBe(
      "http://localhost:3000/auth/callback?next=%2Fmatches",
    );
  });

  it("no puede llevar a otro dominio aunque el destino lo intente", async () => {
    // `next` es una ruta relativa dentro de la URL del propio origen: aunque
    // llegue un destino absoluto, sale como parámetro y `/auth/callback` lo
    // vuelve a sanear antes de navegar.
    await iniciarSesionConGoogle("https://sitio-falso.cl");

    const destino = new URL(signInWithOAuth.mock.calls[0][0].options.redirectTo);
    expect(destino.origin).toBe("http://localhost:3000");
    expect(destino.pathname).toBe("/auth/callback");
  });
});

describe("reenviarConfirmacion", () => {
  it("reenvía el correo de registro con el mismo destino", async () => {
    await reenviarConfirmacion("ana@ejemplo.cl");

    expect(resend.mock.calls[0][0]).toMatchObject({
      type: "signup",
      email: "ana@ejemplo.cl",
    });
    expect(resend.mock.calls[0][0].options.emailRedirectTo).toBe(
      "http://localhost:3000/auth/confirm",
    );
  });
});
