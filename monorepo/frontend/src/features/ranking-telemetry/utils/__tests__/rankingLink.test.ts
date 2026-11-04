import { describe, expect, it } from "vitest";
import { cardRanking, parseRankingContext, tenderDetailHref } from "../rankingLink";

const RK = "0b6f3d2e-8f1a-4c53-9a6e-2d1c7b9e4a10";

describe("tenderDetailHref", () => {
  it("sin ranking es la ruta de siempre", () => {
    expect(tenderDetailHref("t-1", null)).toBe("/matches/t-1");
  });

  it("con ranking agrega r y p", () => {
    expect(tenderDetailHref("t-1", { rankingId: RK, position: 3 })).toBe(
      `/matches/t-1?r=${RK}&p=3`,
    );
  });
});

describe("parseRankingContext", () => {
  it("lee un uuid y una posición válida", () => {
    expect(parseRankingContext(RK, "3")).toEqual({ rankingId: RK, position: 3 });
  });

  it.each([
    ["uuid inválido", "no-uuid", "3"],
    ["posición cero", RK, "0"],
    ["posición decimal", RK, "2.5"],
    ["posición ausente", RK, undefined],
    ["posición mayor a 100", RK, "101"],
    ["parámetro repetido", [RK, RK], "1"],
  ])("devuelve null con %s", (_nombre, r, p) => {
    expect(parseRankingContext(r as string | string[] | undefined, p as string | undefined)).toBeNull();
  });
});

describe("cardRanking", () => {
  it("sin ranking_id (backend anterior o track=false) es null", () => {
    expect(cardRanking(null, 1, "inicio")).toBeNull();
    expect(cardRanking(undefined, 1, "inicio")).toBeNull();
  });

  it("con ranking_id arma el contexto de la tarjeta", () => {
    expect(cardRanking(RK, 2, "matches")).toEqual({
      rankingId: RK,
      position: 2,
      source: "matches",
    });
  });
});
