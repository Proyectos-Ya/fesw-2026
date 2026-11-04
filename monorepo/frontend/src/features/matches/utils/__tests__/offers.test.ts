import { describe, expect, it } from "vitest";

import { formatOffersCount, offersSummary } from "../offers";

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

describe("offersSummary", () => {
  it("en primer llamado muestra la cifra tal cual, sin desglose", () => {
    expect(
      offersSummary({ call_number: 1, received_offers_count: 3, first_call_offers_count: 3 }),
    ).toEqual({ value: "3 cotizaciones" });
  });

  it("sin llamado conocido también muestra la cifra tal cual", () => {
    expect(offersSummary({ call_number: null, received_offers_count: 0 })).toEqual({
      value: "0 cotizaciones",
    });
  });

  it("en segundo llamado suma los dos y desglosa", () => {
    expect(
      offersSummary({ call_number: 2, received_offers_count: 2, first_call_offers_count: 5 }),
    ).toEqual({ value: "7 cotizaciones", detail: "5 en el 1.er llamado y 2 en el 2.º" });
  });

  it("un 0 en el segundo llamado sigue sumando el primero", () => {
    expect(
      offersSummary({ call_number: 2, received_offers_count: 0, first_call_offers_count: 5 }),
    ).toEqual({ value: "5 cotizaciones", detail: "5 en el 1.er llamado y 0 en el 2.º" });
  });

  it("sin la cifra del primer llamado no la inventa", () => {
    expect(
      offersSummary({ call_number: 2, received_offers_count: 2, first_call_offers_count: null }),
    ).toEqual({ value: "2 en el 2.º llamado", detail: "1.er llamado: No disponible" });
  });

  it("sin la cifra del llamado actual no hay nada que mostrar", () => {
    expect(
      offersSummary({ call_number: 2, received_offers_count: null, first_call_offers_count: 5 }),
    ).toEqual({ value: "No disponible" });
  });
});
