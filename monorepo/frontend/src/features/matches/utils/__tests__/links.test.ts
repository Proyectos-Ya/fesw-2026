import { describe, expect, it } from "vitest";
import { compraAgilFichaUrl } from "../links";

describe("compraAgilFichaUrl", () => {
  it("genera la URL de la ficha pública del buscador de Compra Ágil", () => {
    expect(compraAgilFichaUrl("594965-23-COT26")).toBe(
      "https://buscador.mercadopublico.cl/ficha?code=594965-23-COT26",
    );
  });

  it("codifica caracteres especiales del código", () => {
    expect(compraAgilFichaUrl("123 456&x")).toBe(
      "https://buscador.mercadopublico.cl/ficha?code=123%20456%26x",
    );
  });
});
