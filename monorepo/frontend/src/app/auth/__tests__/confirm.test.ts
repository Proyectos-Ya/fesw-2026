/**
 * El enlace del correo de confirmación.
 *
 * Depende de la plantilla propia de `supabase/templates/confirm.html`: la de
 * fábrica consume el token del lado de Supabase y acá no llegaría `token_hash`.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import type { NextRequest } from "next/server";

const verifyOtp = vi.fn();

vi.mock("@/features/auth/supabase/server", () => ({
  crearClienteServidor: async () => ({ auth: { verifyOtp } }),
}));

import { GET } from "../confirm/route";

function peticion(query: string): NextRequest {
  return {
    url: `https://app.vercel.app/auth/confirm${query}`,
  } as unknown as NextRequest;
}

beforeEach(() => {
  verifyOtp.mockReset().mockResolvedValue({ error: null });
});

describe("/auth/confirm", () => {
  it("confirma el correo y deja al usuario dentro", async () => {
    const respuesta = await GET(peticion("?token_hash=abc&type=email"));

    expect(verifyOtp).toHaveBeenCalledWith({ type: "email", token_hash: "abc" });
    expect(respuesta.headers.get("location")).toBe("https://app.vercel.app/");
  });

  it("descarta un destino externo", async () => {
    const respuesta = await GET(
      peticion("?token_hash=abc&type=email&next=https%3A%2F%2Fsitio-falso.cl"),
    );

    expect(respuesta.headers.get("location")).toBe("https://app.vercel.app/");
  });

  it("sin token_hash no intenta canjear nada", async () => {
    const respuesta = await GET(peticion("?type=email"));

    expect(verifyOtp).not.toHaveBeenCalled();
    expect(respuesta.headers.get("location")).toContain("/login?error=enlace_invalido");
  });

  it("un enlace vencido lleva a /verificar, que es donde está el reenvío", async () => {
    verifyOtp.mockResolvedValue({ error: { message: "Token has expired" } });

    const respuesta = await GET(peticion("?token_hash=abc&type=email"));

    expect(respuesta.headers.get("location")).toContain("/verificar?error=");
  });
});
