import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TenderCard } from "../TenderCard";
import type { MatchingResult, Tender } from "../../tenderTypes";

const mockTender: Tender = {
  id: "tender-123",
  code: "1234-56-COT26",
  name: "Adquisición de Insumos Médicos",
  description: "Descripción de prueba",
  status_id: 1,
  status_code: "publicada",
  published_at: "2026-06-01T10:00:00Z",
  closing_at: "2026-06-10T18:00:00Z",
  last_change_at: "2026-06-01T10:00:00Z",
  buyer_rut: "12345678-9",
  buyer_name: "Hospital Central",
  buyer_unit: "Abastecimiento",
  region: "Región Metropolitana de Santiago",
  province: "Santiago",
  commune: "Santiago",
  available_amount_clp: 5000000,
  created_at: "2026-06-01T10:00:00Z",
  updated_at: "2026-06-01T10:00:00Z",
  items: [],
};

const mockMatch: MatchingResult = {
  id: "match-123",
  supplier_id: "supplier-123",
  tender_id: "tender-123",
  similarity_score: 0.85,
  reranker_score: 0.85,
  final_score: 0.85,
  model_version: "v1",
  calculated_at: "2026-06-01T10:00:00Z",
  tender: mockTender,
};

describe("TenderCard", () => {
  it("renderiza el medidor de compatibilidad cuando se proporciona un match", () => {
    render(<TenderCard match={mockMatch} />);

    expect(screen.getByText("Alta compatibilidad")).toBeInTheDocument();
    expect(screen.getByText("85")).toBeInTheDocument();
    expect(screen.getByText("%")).toBeInTheDocument();
    expect(screen.getByText("Adquisición de Insumos Médicos")).toBeInTheDocument();
    expect(screen.getByText("Hospital Central")).toBeInTheDocument();
  });

  it("no renderiza el medidor de compatibilidad cuando solo se pasa tender", () => {
    render(<TenderCard tender={mockTender} />);

    expect(screen.queryByText("Alta compatibilidad")).not.toBeInTheDocument();
    expect(screen.queryByText("Baja compatibilidad")).not.toBeInTheDocument();
    expect(screen.queryByText("0%")).not.toBeInTheDocument();
    expect(screen.getByText("Adquisición de Insumos Médicos")).toBeInTheDocument();
    expect(screen.getByText("Hospital Central")).toBeInTheDocument();
  });
});
