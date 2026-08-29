/**
 * El guardia de borde ya no decide nada sobre la sesión.
 *
 * Comprobaba la cookie `access_token`, lo que solo funciona con frontend y
 * backend en el mismo dominio. En producción están separados —Vercel y
 * Railway—, la cookie pertenece al dominio del backend, y el guardia devolvía
 * al usuario a /login en bucle justo después de iniciar sesión.
 *
 * Estas pruebas fijan que **deja pasar todo**, para que nadie reintroduzca la
 * comprobación sin resolver antes el problema de dominios (ver PENDIENTES 3.9).
 * La protección real vive en el backend y, en el cliente, en `RequireAuth`.
 */

import { describe, expect, it } from "vitest";
import type { NextRequest } from "next/server";
import proxy from "../proxy";

function peticion(pathname: string, conCookie: boolean): NextRequest {
  return {
    nextUrl: { pathname, search: "" },
    url: `https://app.vercel.app${pathname}`,
    cookies: { has: () => conCookie },
  } as unknown as NextRequest;
}

describe("guardia de borde", () => {
  it.each([
    ["/", false],
    ["/matches", false],
    ["/configuracion/notificaciones", false],
    ["/login", false],
    ["/register", false],
    ["/", true],
    ["/login", true],
  ])("deja pasar %s (cookie visible: %s)", (ruta, conCookie) => {
    const respuesta = proxy(peticion(ruta, conCookie));

    // 200 y sin cabecera de redirección: la petición continúa hacia la página.
    expect(respuesta.status).toBe(200);
    expect(respuesta.headers.get("location")).toBeNull();
  });

  it("no redirige aunque la cookie no exista en una ruta protegida", () => {
    // El caso exacto del bucle: sin cookie visible para el borde, la ruta
    // protegida tiene que servirse igual y dejar que RequireAuth resuelva.
    const respuesta = proxy(peticion("/matches", false));

    expect(respuesta.headers.get("location")).toBeNull();
  });
});
