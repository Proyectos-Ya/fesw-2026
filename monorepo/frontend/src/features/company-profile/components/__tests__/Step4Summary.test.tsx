import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Step4Summary } from "../steps/Step4Summary";
import type { ProfileData } from "../../profileSchema";

function renderSummary(certifications: ProfileData["certifications"]) {
  render(
    <Step4Summary
      data={{
        legal_name: "Constructora Pérez Ltda.",
        rut: "76.123.456-0",
        regions: ["Región Metropolitana"],
        years_experience: 5,
        num_employees: 10,
        sectors: ["Construcción"],
        keywords: [],
        certifications,
        description: "Constructora especializada en obras civiles menores.",
      }}
      onBack={vi.fn()}
      onSubmit={vi.fn()}
      onGoToStep={vi.fn()}
      isLoading={false}
    />,
  );
}

describe("Step4Summary (certificaciones)", () => {
  it("muestra la fecha de vencimiento en formato DD/MM/AAAA", () => {
    renderSummary([{ name: "ISO 9001", expires_at: "2026-12-31" }]);

    expect(screen.getByText("ISO 9001 (Vence: 31/12/2026)")).toBeInTheDocument();
  });

  it("muestra solo el nombre cuando no hay fecha", () => {
    renderSummary([{ name: "SEC", expires_at: null }, "OHSAS 18001"]);

    expect(screen.getByText("SEC")).toBeInTheDocument();
    expect(screen.getByText("OHSAS 18001")).toBeInTheDocument();
    expect(screen.queryByText(/Vence/)).not.toBeInTheDocument();
  });

  it("oculta la sección cuando no hay certificaciones", () => {
    renderSummary([]);

    expect(screen.queryByText("Certificaciones")).not.toBeInTheDocument();
  });
});
