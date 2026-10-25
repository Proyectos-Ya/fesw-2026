import { describe, expect, it } from "vitest";

import { formatOffersCount } from "../offers";

describe("formatOffersCount", () => {
  it("sin cifra dice que no está disponible, no 0", () => {
    expect(formatOffersCount(null)).toBe("No disponible");
    expect(formatOffersCount(undefined)).toBe("No disponible");
  });

  it("0 es una cifra real", () => {
    expect(formatOffersCount(0)).toBe("0 cotizaciones");
  });

  it("1 va en singular", () => {
    expect(formatOffersCount(1)).toBe("1 cotización");
  });

  it("cualquier otra cifra va en plural", () => {
    expect(formatOffersCount(17)).toBe("17 cotizaciones");
  });
});
