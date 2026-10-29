import { describe, expect, it } from "vitest";
import { REGIONS, toCanonicalRegion, toCanonicalRegions } from "../regions";

describe("lista única de regiones", () => {
  it("tiene las 16 regiones con el nombre canónico que acepta el backend", () => {
    expect(REGIONS).toHaveLength(16);
    expect(REGIONS).toContain("Metropolitana de Santiago");
    expect(REGIONS).toContain("Libertador General Bernardo O'Higgins");
    expect(REGIONS).toContain("Aysén del General Carlos Ibáñez del Campo");
    expect(REGIONS).toContain("Magallanes y de la Antártica Chilena");
  });

  it("no tiene nombres repetidos", () => {
    expect(new Set(REGIONS).size).toBe(REGIONS.length);
  });
});

describe("nombres de regiones guardados antes de unificar la lista", () => {
  it("convierte los cuatro nombres cortos al canónico", () => {
    expect(toCanonicalRegion("Metropolitana")).toBe("Metropolitana de Santiago");
    expect(toCanonicalRegion("O'Higgins")).toBe(
      "Libertador General Bernardo O'Higgins"
    );
    expect(toCanonicalRegion("Aysén")).toBe(
      "Aysén del General Carlos Ibáñez del Campo"
    );
    expect(toCanonicalRegion("Magallanes")).toBe(
      "Magallanes y de la Antártica Chilena"
    );
  });

  it("deja igual las que ya son canónicas", () => {
    expect(toCanonicalRegion("Valparaíso")).toBe("Valparaíso");
    expect(toCanonicalRegion("Metropolitana de Santiago")).toBe(
      "Metropolitana de Santiago"
    );
  });

  it("devuelve null si no reconoce la región", () => {
    expect(toCanonicalRegion("Región inventada")).toBeNull();
  });

  it("descarta las desconocidas y no repite", () => {
    expect(
      toCanonicalRegions([
        "Metropolitana",
        "Metropolitana de Santiago",
        "Región inventada",
        "Biobío",
      ])
    ).toEqual(["Metropolitana de Santiago", "Biobío"]);
  });
});
