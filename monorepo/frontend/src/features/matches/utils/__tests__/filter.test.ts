import { describe, expect, it } from "vitest";
import type { MatchingResult, Tender } from "../../tenderTypes";
import {
  EMPTY_BUDGET_RANGE,
  filterMatchesByBudget,
  filterMatchesByProvince,
  isBudgetFilterActive,
  listProvinces,
  tenderMatchesBudget,
} from "../filter";

function makeTender(overrides: Partial<Tender> = {}): Tender {
  return {
    id: "t-1",
    code: "1057539-228-COT26",
    name: "Compra de insumos",
    description: null,
    status_id: 1,
    status_code: "publicada",
    published_at: "2026-06-01T00:00:00Z",
    closing_at: "2026-06-20T00:00:00Z",
    last_change_at: "2026-06-01T00:00:00Z",
    buyer_rut: "61.000.000-0",
    buyer_name: "Municipalidad de Prueba",
    buyer_unit: "Adquisiciones",
    province: "Santiago",
    available_amount_clp: 5_000_000,
    created_at: "2026-06-01T00:00:00Z",
    updated_at: "2026-06-01T00:00:00Z",
    items: [],
    ...overrides,
  };
}

function makeMatch(
  id: string,
  tenderOverrides: Partial<Tender> | null = {},
): MatchingResult {
  return {
    id,
    supplier_id: "s-1",
    tender_id: `tender-${id}`,
    similarity_score: 0.8,
    reranker_score: null,
    final_score: 0.8,
    model_version: "v1",
    calculated_at: "2026-06-05T00:00:00Z",
    tender: tenderOverrides === null ? null : makeTender(tenderOverrides),
  };
}

describe("budget filter", () => {
  it("sin filtro activo deja pasar todo", () => {
    expect(isBudgetFilterActive(EMPTY_BUDGET_RANGE)).toBe(false);
    expect(tenderMatchesBudget(makeTender(), EMPTY_BUDGET_RANGE)).toBe(true);
  });

  it("filtra por rango inclusivo y rechaza montos desconocidos", () => {
    const matches = [
      makeMatch("a", { available_amount_clp: 1_000_000 }),
      makeMatch("b", { available_amount_clp: 5_000_000 }),
      makeMatch("c", { available_amount_clp: null }),
    ];
    const result = filterMatchesByBudget(matches, { min: 2_000_000, max: 5_000_000 });
    expect(result.map((m) => m.id)).toEqual(["b"]);
  });
});

describe("province filter", () => {
  const matches = [
    makeMatch("a", { province: "Santiago" }),
    makeMatch("b", { province: "Cordillera" }),
    makeMatch("c", { province: "santiago" }),
    makeMatch("d", { province: null }),
    makeMatch("e", null),
  ];

  it("sin provincia seleccionada deja pasar todo", () => {
    expect(filterMatchesByProvince(matches, null)).toEqual(matches);
  });

  it("filtra por provincia sin distinguir mayúsculas", () => {
    const result = filterMatchesByProvince(matches, "Santiago");
    expect(result.map((m) => m.id)).toEqual(["a", "c"]);
  });

  it("excluye licitaciones sin provincia o sin tender cuando el filtro está activo", () => {
    const result = filterMatchesByProvince(matches, "Cordillera");
    expect(result.map((m) => m.id)).toEqual(["b"]);
  });

  it("lista provincias únicas ordenadas alfabéticamente", () => {
    expect(listProvinces(matches)).toEqual(["Cordillera", "Santiago"]);
  });
});
