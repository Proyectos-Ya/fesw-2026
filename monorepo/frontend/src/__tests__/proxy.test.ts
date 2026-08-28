import { describe, expect, it } from "vitest";
import { NextRequest } from "next/server";
import proxy from "@/proxy";

function makeRequest(path: string, withCookie: boolean): NextRequest {
  return new NextRequest(`http://localhost:3000${path}`, {
    headers: withCookie ? { cookie: "access_token=jwt-de-prueba" } : {},
  });
}

describe("proxy (guardia de autenticación)", () => {
  it("redirige a /login cuando no hay cookie de sesión en una ruta protegida", () => {
    const response = proxy(makeRequest("/", false));

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("http://localhost:3000/login");
  });

  it("permite pasar a /login sin cookie de sesión", () => {
    const response = proxy(makeRequest("/login", false));

    expect(response.headers.get("location")).toBeNull();
  });

  it("permite pasar a /register sin cookie de sesión", () => {
    const response = proxy(makeRequest("/register", false));

    expect(response.headers.get("location")).toBeNull();
  });

  it("deja entrar al home cuando hay cookie de sesión", () => {
    const response = proxy(makeRequest("/", true));

    expect(response.headers.get("location")).toBeNull();
  });

  it("redirige al home cuando un usuario con sesión visita /login", () => {
    const response = proxy(makeRequest("/login", true));

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("http://localhost:3000/");
  });

  it("redirige al home cuando un usuario con sesión visita /register", () => {
    const response = proxy(makeRequest("/register", true));

    expect(response.headers.get("location")).toBe("http://localhost:3000/");
  });

  it("conserva el destino al redirigir una ruta profunda a /login", () => {
    // Es el enlace de un correo de alerta: sin el parámetro, tras iniciar
    // sesión el usuario aterrizaría en el home y tendría que volver al correo.
    const response = proxy(makeRequest("/matches/abc-123", false));

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(
      "http://localhost:3000/login?next=%2Fmatches%2Fabc-123",
    );
  });

  it("incluye la query del destino en el parámetro de retorno", () => {
    const response = proxy(makeRequest("/matches?region=RM", false));

    expect(response.headers.get("location")).toBe(
      "http://localhost:3000/login?next=%2Fmatches%3Fregion%3DRM",
    );
  });
});
