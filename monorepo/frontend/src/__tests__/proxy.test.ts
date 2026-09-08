/**
 * El guardia de borde vuelve a decidir, y este archivo fija por qué puede.
 *
 * Estuvo desactivado por una razón concreta: comprobaba la cookie
 * `access_token`, que emitía el backend en Railway para su propio dominio, así
 * que el borde de Vercel no la veía nunca y devolvía al login en bucle a quien
 * acababa de entrar (PENDIENTES 3.9). Con Supabase Auth la sesión se resuelve
 * con `getUser()`, que revalida contra Supabase, y no mirando si hay una cookie
 * de otro dominio.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import type { NextRequest } from "next/server";

const getUser = vi.fn();

vi.mock("@supabase/ssr", () => ({
  createServerClient: () => ({ auth: { getUser } }),
}));

import proxy from "../proxy";

function peticion(pathname: string, search = ""): NextRequest {
  const url = new URL(`https://app.vercel.app${pathname}${search}`);
  return {
    nextUrl: url,
    url: url.toString(),
    headers: new Headers(),
    cookies: { getAll: () => [], set: () => {} },
  } as unknown as NextRequest;
}

function conSesion() {
  getUser.mockResolvedValue({ data: { user: { id: "abc" } } });
}

function sinSesion() {
  getUser.mockResolvedValue({ data: { user: null } });
}

beforeEach(() => {
  getUser.mockReset();
});

describe("guardia de borde", () => {
  it.each(["/", "/matches", "/configuracion/notificaciones"])(
    "deja pasar %s cuando hay sesión",
    async (ruta) => {
      conSesion();

      const respuesta = await proxy(peticion(ruta));

      expect(respuesta.headers.get("location")).toBeNull();
    },
  );

  it.each(["/matches", "/configuracion/notificaciones"])(
    "manda a login desde %s cuando no hay sesión",
    async (ruta) => {
      sinSesion();

      const respuesta = await proxy(peticion(ruta));

      expect(respuesta.headers.get("location")).toContain("/login");
    },
  );

  it("conserva el destino para volver después de iniciar sesión", async () => {
    sinSesion();

    const respuesta = await proxy(peticion("/matches"));

    expect(respuesta.headers.get("location")).toContain("next=%2Fmatches");
  });

  it.each(["/login", "/register", "/verificar", "/auth/callback", "/auth/confirm"])(
    "deja pasar %s sin sesión",
    async (ruta) => {
      sinSesion();

      const respuesta = await proxy(peticion(ruta));

      expect(respuesta.headers.get("location")).toBeNull();
    },
  );

  it("no redirige en la raíz sin sesión hacia un login con next", async () => {
    // `loginUrlWithReturn` omite el parámetro cuando el destino es la raíz: no
    // aporta nada y ensucia la URL que ve el usuario.
    sinSesion();

    const respuesta = await proxy(peticion("/"));

    expect(respuesta.headers.get("location")).toMatch(/\/login$/);
  });
});
