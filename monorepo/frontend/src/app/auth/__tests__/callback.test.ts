/**
 * El callback de OAuth es mejor blanco para un open redirect que el propio
 * login: la URL la arma el proveedor, el usuario la ve venir de un dominio en
 * el que confía, y el parámetro `next` viaja intacto hasta acá.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import type { NextRequest } from "next/server";

const exchangeCodeForSession = vi.fn();

vi.mock("@/features/auth/supabase/server", () => ({
  crearClienteServidor: async () => ({ auth: { exchangeCodeForSession } }),
}));

import { GET } from "../callback/route";

function peticion(query: string): NextRequest {
  return {
    url: `https://app.vercel.app/auth/callback${query}`,
  } as unknown as NextRequest;
}

beforeEach(() => {
  exchangeCodeForSession.mockReset().mockResolvedValue({ error: null });
});

describe("/auth/callback", () => {
  it("canjea el código y vuelve al home", async () => {
    const respuesta = await GET(peticion("?code=abc"));

    expect(exchangeCodeForSession).toHaveBeenCalledWith("abc");
    expect(respuesta.headers.get("location")).toBe("https://app.vercel.app/");
  });

  it("respeta un destino interno", async () => {
    const respuesta = await GET(peticion("?code=abc&next=%2Fmatches"));

    expect(respuesta.headers.get("location")).toBe("https://app.vercel.app/matches");
  });

  it.each([
    "https%3A%2F%2Fsitio-falso.cl",
    "%2F%2Fsitio-falso.cl",
    "%2F%5Csitio-falso.cl",
  ])("descarta el destino externo %s", async (destino) => {
    const respuesta = await GET(peticion(`?code=abc&next=${destino}`));

    expect(respuesta.headers.get("location")).toBe("https://app.vercel.app/");
  });

  it("manda al login cuando el proveedor devuelve un error", async () => {
    const respuesta = await GET(peticion("?error=access_denied"));

    expect(exchangeCodeForSession).not.toHaveBeenCalled();
    expect(respuesta.headers.get("location")).toContain("/login?error=");
  });

  it("manda al login cuando falla el canje", async () => {
    exchangeCodeForSession.mockResolvedValue({ error: { message: "código usado" } });

    const respuesta = await GET(peticion("?code=abc"));

    expect(respuesta.headers.get("location")).toContain("/login?error=");
  });
});
