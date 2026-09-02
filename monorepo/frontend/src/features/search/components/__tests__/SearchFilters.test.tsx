import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SearchFilters } from "../SearchFilters";

describe("SearchFilters", () => {
  it("despliega los filtros al hacer click en el botón de filtros avanzados", () => {
    render(
      <SearchFilters
        regions={[]}
        onRegionsChange={vi.fn()}
        availability={null}
        onAvailabilityChange={vi.fn()}
        onAmountRangeChange={vi.fn()}
        onClearFilters={vi.fn()}
        hasActiveFilters={false}
      />,
    );

    expect(screen.queryByText(/Estado de postulación/i)).not.toBeInTheDocument();

    const toggleButton = screen.getByRole("button", { name: /filtros avanzados/i });
    fireEvent.click(toggleButton);

    expect(screen.getByText(/Estado de postulación/i)).toBeInTheDocument();
    expect(screen.getByText(/Monto estimado \(CLP\)/i)).toBeInTheDocument();
  });

  it("permite seleccionar y deseleccionar regiones", () => {
    const handleRegionsChange = vi.fn();
    render(
      <SearchFilters
        regions={["Valparaíso"]}
        onRegionsChange={handleRegionsChange}
        availability={null}
        onAvailabilityChange={vi.fn()}
        onAmountRangeChange={vi.fn()}
        onClearFilters={vi.fn()}
        hasActiveFilters={true}
      />,
    );

    // Open filters
    fireEvent.click(screen.getByRole("button", { name: /filtros avanzados/i }));

    // Click on "Metropolitana de Santiago" to add it
    const metroButton = screen.getByRole("button", { name: /Metropolitana de Santiago/i });
    fireEvent.click(metroButton);
    expect(handleRegionsChange).toHaveBeenCalledWith(["Valparaíso", "Metropolitana de Santiago"]);

    // Click on "Valparaíso" to remove it
    const valpoButton = screen.getByRole("button", { name: /Valparaíso/i });
    fireEvent.click(valpoButton);
    expect(handleRegionsChange).toHaveBeenCalledWith([]);
  });

  it("permite alternar el filtro de disponibilidad (vigentes / cerradas)", () => {
    const handleAvailabilityChange = vi.fn();
    render(
      <SearchFilters
        regions={[]}
        onRegionsChange={vi.fn()}
        availability={null}
        onAvailabilityChange={handleAvailabilityChange}
        onAmountRangeChange={vi.fn()}
        onClearFilters={vi.fn()}
        hasActiveFilters={false}
      />,
    );

    // Open filters
    fireEvent.click(screen.getByRole("button", { name: /filtros avanzados/i }));

    const vigentesBtn = screen.getByRole("button", { name: /Vigentes/i });
    fireEvent.click(vigentesBtn);
    expect(handleAvailabilityChange).toHaveBeenCalledWith("vigentes");
  });

  it("permite aplicar rango de monto", () => {
    const handleAmountChange = vi.fn();
    render(
      <SearchFilters
        regions={[]}
        onRegionsChange={vi.fn()}
        availability={null}
        onAvailabilityChange={vi.fn()}
        onAmountRangeChange={handleAmountChange}
        onClearFilters={vi.fn()}
        hasActiveFilters={false}
      />,
    );

    // Open filters
    fireEvent.click(screen.getByRole("button", { name: /filtros avanzados/i }));

    const minInput = screen.getByPlaceholderText("$ 0");
    const maxInput = screen.getByPlaceholderText("$ Sin límite");

    fireEvent.change(minInput, { target: { value: "500000" } });
    fireEvent.change(maxInput, { target: { value: "2000000" } });

    const applyButton = screen.getByRole("button", { name: /aplicar montos/i });
    fireEvent.click(applyButton);

    expect(handleAmountChange).toHaveBeenCalledWith(500000, 2000000);
  });
});
