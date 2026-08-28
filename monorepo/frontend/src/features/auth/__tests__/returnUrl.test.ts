import { describe, expect, it } from "vitest";
import { loginUrlWithReturn, sanitizeReturnUrl } from "../returnUrl";

describe("sanitizeReturnUrl", () => {
  it("acepta una ruta interna", () => {
    expect(sanitizeReturnUrl("/matches/abc-123")).toBe("/matches/abc-123");
  });

  it("conserva la query del destino", () => {
    expect(sanitizeReturnUrl("/matches?filtro=verde")).toBe("/matches?filtro=verde");
  });

  it.each([null, undefined, ""])("descarta un valor vacío (%s)", (valor) => {
    expect(sanitizeReturnUrl(valor)).toBeNull();
  });

  // Sin estas comprobaciones, /login se convertiría en un redirector hacia
  // cualquier dominio: es la puerta clásica del phishing.
  it.each([
    "https://sitio-falso.cl",
    "http://sitio-falso.cl",
    "//sitio-falso.cl",
    "/\\sitio-falso.cl",
    "javascript:alert(1)",
    "matches/abc",
  ])("descarta el destino externo o relativo %s", (valor) => {
    expect(sanitizeReturnUrl(valor)).toBeNull();
  });
});

describe("loginUrlWithReturn", () => {
  it("agrega el destino al que volver", () => {
    expect(loginUrlWithReturn("/matches/abc-123")).toBe(
      "/login?next=%2Fmatches%2Fabc-123",
    );
  });

  it("incluye la query del destino", () => {
    expect(loginUrlWithReturn("/matches", "?region=RM")).toBe(
      "/login?next=%2Fmatches%3Fregion%3DRM",
    );
  });

  it("no agrega parámetro cuando el destino es el home", () => {
    // Volver al home es lo que login ya hace por defecto.
    expect(loginUrlWithReturn("/")).toBe("/login");
  });

  it("no se apunta a sí mismo", () => {
    expect(loginUrlWithReturn("/login")).toBe("/login");
  });

  it("el destino codificado se recupera intacto", () => {
    const url = new URL(loginUrlWithReturn("/matches/abc-123"), "http://localhost");

    expect(sanitizeReturnUrl(url.searchParams.get("next"))).toBe("/matches/abc-123");
  });
});
