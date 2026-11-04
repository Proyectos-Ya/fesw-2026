import { describe, expect, it } from "vitest";

import { formatDeliveryAddress, formatDeliveryTerm } from "../entrega";

describe("formatDeliveryAddress", () => {
  it("muestra la dirección tal cual", () => {
    expect(formatDeliveryAddress("SERVIU REGION DE AYSEN RAMON FREIRE 5")).toBe(
      "SERVIU REGION DE AYSEN RAMON FREIRE 5",
    );
  });

  it("sin dirección usa el texto de HU-22", () => {
    expect(formatDeliveryAddress(null)).toBe("Dirección de entrega no disponible");
    expect(formatDeliveryAddress(undefined)).toBe("Dirección de entrega no disponible");
    expect(formatDeliveryAddress("   ")).toBe("Dirección de entrega no disponible");
  });
});

describe("formatDeliveryTerm", () => {
  it("1 va en singular", () => {
    expect(formatDeliveryTerm(1)).toBe("1 día");
  });

  it("cualquier otra cifra va en plural, 0 incluido", () => {
    expect(formatDeliveryTerm(0)).toBe("0 días");
    expect(formatDeliveryTerm(5)).toBe("5 días");
  });

  it("sin plazo no inventa un 0", () => {
    expect(formatDeliveryTerm(null)).toBe("Plazo de entrega no disponible");
    expect(formatDeliveryTerm(undefined)).toBe("Plazo de entrega no disponible");
  });
});
