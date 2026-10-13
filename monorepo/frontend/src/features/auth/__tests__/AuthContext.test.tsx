import React from "react";
import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider, useAuth } from "../AuthContext";
import type { UserPublic } from "../authSchema";
import { getMe } from "../services/authService";

type Evento = "INITIAL_SESSION" | "SIGNED_IN" | "TOKEN_REFRESHED" | "USER_UPDATED" | "SIGNED_OUT";
type Sesion = { user: { id: string }; access_token: string } | null;
type Callback = (evento: Evento, sesion: Sesion) => void;

let emitir: Callback = () => {};

// Cliente de Supabase mínimo: guarda el callback de `onAuthStateChange` para que
// cada prueba emita los eventos que necesita, como lo haría auth-js.
vi.mock("../supabase/client", () => ({
  crearClienteNavegador: () => ({
    auth: {
      getSession: async () => ({ data: { session: null } }),
      onAuthStateChange: (cb: Callback) => {
        emitir = cb;
        return { data: { subscription: { unsubscribe: () => {} } } };
      },
    },
  }),
}));

vi.mock("../services/authService", () => ({
  getMe: vi.fn(),
  cerrarSesion: vi.fn(),
}));

const PERFIL: UserPublic = {
  id: "user-1",
  email: "ana@example.com",
  full_name: "Ana Pérez",
  phone: null,
  active: true,
  email_verified: true,
  created_at: "2026-01-01T00:00:00Z",
};

function sesionDe(authId: string): Sesion {
  return { user: { id: authId }, access_token: "token" };
}

function Usuario() {
  const { user } = useAuth();
  return <span>{user?.email ?? "sin usuario"}</span>;
}

async function montarConSesion(authId: string) {
  render(
    <AuthProvider>
      <Usuario />
    </AuthProvider>,
  );
  await act(async () => emitir("INITIAL_SESSION", sesionDe(authId)));
  await screen.findByText(PERFIL.email);
}

describe("AuthProvider: eventos de Supabase", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getMe).mockResolvedValue(PERFIL);
  });

  it("carga el perfil con la sesión inicial", async () => {
    await montarConSesion("auth-1");

    expect(getMe).toHaveBeenCalledTimes(1);
  });

  it("no vuelve a pedir el perfil cuando SIGNED_IN repite la misma sesión", async () => {
    // auth-js emite SIGNED_IN cada vez que la pestaña vuelve a estar visible.
    await montarConSesion("auth-1");

    await act(async () => emitir("SIGNED_IN", sesionDe("auth-1")));

    expect(getMe).toHaveBeenCalledTimes(1);
  });

  it("pide el perfil cuando SIGNED_IN trae a otro usuario", async () => {
    await montarConSesion("auth-1");

    await act(async () => emitir("SIGNED_IN", sesionDe("auth-2")));

    await waitFor(() => expect(getMe).toHaveBeenCalledTimes(2));
  });

  it("pide el perfil cuando el usuario cambió sus datos", async () => {
    await montarConSesion("auth-1");

    await act(async () => emitir("USER_UPDATED", sesionDe("auth-1")));

    await waitFor(() => expect(getMe).toHaveBeenCalledTimes(2));
  });

  it("después de cerrar sesión, volver a entrar con el mismo usuario carga el perfil", async () => {
    await montarConSesion("auth-1");

    await act(async () => emitir("SIGNED_OUT", null));
    await screen.findByText("sin usuario");
    await act(async () => emitir("SIGNED_IN", sesionDe("auth-1")));

    await screen.findByText(PERFIL.email);
    expect(getMe).toHaveBeenCalledTimes(2);
  });
});
