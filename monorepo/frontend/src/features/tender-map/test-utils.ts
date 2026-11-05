import type { TenderMapPoint, TenderMapResult } from "./types";

export function buildTenderMapPoint(overrides: Partial<TenderMapPoint> = {}): TenderMapPoint {
  return {
    id: "t-1",
    name: "Insumos de aseo",
    buyer_name: "Municipalidad de Ancud",
    delivery_address: "Yerbas Buenas #915",
    closing_at: "2026-11-03T18:00:00Z",
    lat: -41.87,
    lng: -73.82,
    precision: "direccion",
    ...overrides,
  };
}

export function buildTenderMapResult(overrides: Partial<TenderMapResult> = {}): TenderMapResult {
  return {
    region: "Los Lagos",
    items: [buildTenderMapPoint()],
    total: 1,
    is_truncated: false,
    ...overrides,
  };
}
