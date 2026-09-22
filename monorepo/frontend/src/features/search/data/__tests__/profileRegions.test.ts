import { describe, expect, it } from "vitest";
import { PROFILE_REGIONS, toSearchRegion, toSearchRegions } from "../profileRegions";
import { SEARCH_REGIONS } from "../searchConstants";

describe("regiones del perfil en el buscador", () => {
  it("todas las regiones del perfil tienen nombre en el buscador", () => {
    // Si alguna se queda sin traducción, el filtro por defecto la descarta y
    // el usuario busca en menos regiones de las que declaró.
    const sinTraduccion = PROFILE_REGIONS.filter(
      (region) => toSearchRegion(region) === null
    );

    expect(sinTraduccion).toEqual([]);
  });

  it("traduce las cuatro que se escriben distinto", () => {
    expect(toSearchRegion("Metropolitana")).toBe("Metropolitana de Santiago");
    expect(toSearchRegion("O'Higgins")).toBe(
      "Libertador General Bernardo O'Higgins"
    );
    expect(toSearchRegion("Aysén")).toBe(
      "Aysén del General Carlos Ibáñez del Campo"
    );
    expect(toSearchRegion("Magallanes")).toBe(
      "Magallanes y de la Antártica Chilena"
    );
  });

  it("deja igual las que ya coinciden", () => {
    expect(toSearchRegion("Valparaíso")).toBe("Valparaíso");
    expect(toSearchRegion("Los Lagos")).toBe("Los Lagos");
  });

  it("devuelve solo nombres que el buscador conoce y sin repetir", () => {
    const traducidas = toSearchRegions([
      "Metropolitana",
      "Metropolitana de Santiago",
      "Región inventada",
      "Biobío",
    ]);

    expect(traducidas).toEqual(["Metropolitana de Santiago", "Biobío"]);
    expect(traducidas.every((r) => SEARCH_REGIONS.includes(r))).toBe(true);
  });
});
