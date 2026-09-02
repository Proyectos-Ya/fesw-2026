import React from "react";
import { render, screen, fireEvent, within } from "@testing-library/react";
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

  it("permite aplicar rango de fechas de cierre (desde y hasta) (CA-1)", () => {
    const handleDateRangeChange = vi.fn();
    render(
      <SearchFilters
        regions={[]}
        onRegionsChange={vi.fn()}
        availability={null}
        onAvailabilityChange={vi.fn()}
        onClosingDateRangeChange={handleDateRangeChange}
        onAmountRangeChange={vi.fn()}
        onClearFilters={vi.fn()}
        hasActiveFilters={false}
      />,
    );

    // Open filters
    fireEvent.click(screen.getByRole("button", { name: /filtros avanzados/i }));

    const desdeInput = screen.getByLabelText(/fecha de cierre desde/i);
    const hastaInput = screen.getByLabelText(/fecha de cierre hasta/i);

    fireEvent.change(desdeInput, { target: { value: "2026-09-01" } });
    fireEvent.change(hastaInput, { target: { value: "2026-09-15" } });

    const applyButton = screen.getByRole("button", { name: /aplicar fechas/i });
    fireEvent.click(applyButton);

    expect(handleDateRangeChange).toHaveBeenCalledWith("2026-09-01", "2026-09-15");
  });

  it("permite limpiar el rango de fechas cuando está activo (CA-1)", () => {
    const handleDateRangeChange = vi.fn();
    render(
      <SearchFilters
        regions={[]}
        onRegionsChange={vi.fn()}
        availability={null}
        onAvailabilityChange={vi.fn()}
        closingFrom="2026-09-01"
        closingTo="2026-09-15"
        onClosingDateRangeChange={handleDateRangeChange}
        onAmountRangeChange={vi.fn()}
        onClearFilters={vi.fn()}
        hasActiveFilters={true}
      />,
    );

    // Open filters
    fireEvent.click(screen.getByRole("button", { name: /filtros avanzados/i }));

    const clearDatesButton = screen.getByRole("button", { name: /limpiar fechas/i });
    fireEvent.click(clearDatesButton);

    expect(handleDateRangeChange).toHaveBeenCalledWith(undefined, undefined);
  });

  const mockProvinces = [
    { id: 51, name: "Santiago", region_name: "Metropolitana de Santiago" },
    { id: 52, name: "Cordillera", region_name: "Metropolitana de Santiago" },
    { id: 53, name: "Valparaíso", region_name: "Valparaíso" },
  ];

  const mockCommunes = [
    { id: 295, name: "Santiago", province_name: "Santiago" },
    { id: 296, name: "Providencia", province_name: "Santiago" },
    { id: 300, name: "Puente Alto", province_name: "Cordillera" },
    { id: 301, name: "Viña del Mar", province_name: "Valparaíso" },
  ];

  it("deshabilita los selectores de provincia y comuna si no hay región seleccionada", () => {
    render(
      <SearchFilters
        regions={[]}
        onRegionsChange={vi.fn()}
        availability={null}
        onAvailabilityChange={vi.fn()}
        onAmountRangeChange={vi.fn()}
        onClearFilters={vi.fn()}
        hasActiveFilters={false}
        provinces={mockProvinces}
        communes={mockCommunes}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /filtros avanzados/i }));

    const provinceSelect = screen.getByLabelText(/^provincia$/i);
    const communeSelect = screen.getByLabelText(/^comuna$/i);

    expect(provinceSelect).toBeDisabled();
    expect(communeSelect).toBeDisabled();
  });

  it("habilita provincia y filtra según region_name cuando hay una región seleccionada", () => {
    render(
      <SearchFilters
        regions={["Metropolitana de Santiago"]}
        onRegionsChange={vi.fn()}
        availability={null}
        onAvailabilityChange={vi.fn()}
        onAmountRangeChange={vi.fn()}
        onClearFilters={vi.fn()}
        hasActiveFilters={true}
        provinces={mockProvinces}
        communes={mockCommunes}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /filtros avanzados/i }));

    const provinceSelect = screen.getByLabelText(/^provincia$/i);
    const communeSelect = screen.getByLabelText(/^comuna$/i);

    expect(provinceSelect).not.toBeDisabled();
    expect(communeSelect).toBeDisabled();

    // Santiago y Cordillera pertenecen a Metropolitana de Santiago
    expect(within(provinceSelect).getByRole("option", { name: "Santiago" })).toBeInTheDocument();
    expect(within(provinceSelect).getByRole("option", { name: "Cordillera" })).toBeInTheDocument();
    // Valparaíso no debe estar disponible en las opciones
    expect(within(provinceSelect).queryByRole("option", { name: "Valparaíso" })).not.toBeInTheDocument();
  });

  it("habilita comuna y filtra según province_name cuando hay provincia seleccionada", () => {
    render(
      <SearchFilters
        regions={["Metropolitana de Santiago"]}
        onRegionsChange={vi.fn()}
        provinceId={51}
        onProvinceChange={vi.fn()}
        availability={null}
        onAvailabilityChange={vi.fn()}
        onAmountRangeChange={vi.fn()}
        onClearFilters={vi.fn()}
        hasActiveFilters={true}
        provinces={mockProvinces}
        communes={mockCommunes}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /filtros avanzados/i }));

    const communeSelect = screen.getByLabelText(/^comuna$/i);
    expect(communeSelect).not.toBeDisabled();

    // Santiago y Providencia pertenecen a provincia Santiago
    expect(within(communeSelect).getByRole("option", { name: "Santiago" })).toBeInTheDocument();
    expect(within(communeSelect).getByRole("option", { name: "Providencia" })).toBeInTheDocument();
    // Puente Alto (Cordillera) y Viña del Mar (Valparaíso) no deben estar
    expect(within(communeSelect).queryByRole("option", { name: "Puente Alto" })).not.toBeInTheDocument();
    expect(within(communeSelect).queryByRole("option", { name: "Viña del Mar" })).not.toBeInTheDocument();
  });

  it("llama a onProvinceChange y resetea comuna al seleccionar una provincia", () => {
    const handleProvinceChange = vi.fn();
    const handleCommuneChange = vi.fn();

    render(
      <SearchFilters
        regions={["Metropolitana de Santiago"]}
        onRegionsChange={vi.fn()}
        provinceId={51}
        onProvinceChange={handleProvinceChange}
        communeId={295}
        onCommuneChange={handleCommuneChange}
        availability={null}
        onAvailabilityChange={vi.fn()}
        onAmountRangeChange={vi.fn()}
        onClearFilters={vi.fn()}
        hasActiveFilters={true}
        provinces={mockProvinces}
        communes={mockCommunes}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /filtros avanzados/i }));

    const provinceSelect = screen.getByLabelText(/^provincia$/i);
    fireEvent.change(provinceSelect, { target: { value: "52" } });

    expect(handleProvinceChange).toHaveBeenCalledWith(52);
    expect(handleCommuneChange).toHaveBeenCalledWith(undefined);
  });

  it("llama a onCommuneChange al seleccionar una comuna", () => {
    const handleCommuneChange = vi.fn();

    render(
      <SearchFilters
        regions={["Metropolitana de Santiago"]}
        onRegionsChange={vi.fn()}
        provinceId={51}
        onProvinceChange={vi.fn()}
        communeId={295}
        onCommuneChange={handleCommuneChange}
        availability={null}
        onAvailabilityChange={vi.fn()}
        onAmountRangeChange={vi.fn()}
        onClearFilters={vi.fn()}
        hasActiveFilters={true}
        provinces={mockProvinces}
        communes={mockCommunes}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /filtros avanzados/i }));

    const communeSelect = screen.getByLabelText(/^comuna$/i);
    fireEvent.change(communeSelect, { target: { value: "296" } });

    expect(handleCommuneChange).toHaveBeenCalledWith(296);
  });

  it("resetea provincia y comuna cuando la región cambia o se desmarca", () => {
    const handleRegionsChange = vi.fn();
    const handleProvinceChange = vi.fn();
    const handleCommuneChange = vi.fn();

    render(
      <SearchFilters
        regions={["Metropolitana de Santiago"]}
        onRegionsChange={handleRegionsChange}
        provinceId={51}
        onProvinceChange={handleProvinceChange}
        communeId={295}
        onCommuneChange={handleCommuneChange}
        availability={null}
        onAvailabilityChange={vi.fn()}
        onAmountRangeChange={vi.fn()}
        onClearFilters={vi.fn()}
        hasActiveFilters={true}
        provinces={mockProvinces}
        communes={mockCommunes}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /filtros avanzados/i }));

    // Deseleccionar región activa
    const metroButton = screen.getByRole("button", { name: /Metropolitana de Santiago/i });
    fireEvent.click(metroButton);

    expect(handleRegionsChange).toHaveBeenCalledWith([]);
    expect(handleProvinceChange).toHaveBeenCalledWith(undefined);
    expect(handleCommuneChange).toHaveBeenCalledWith(undefined);
  });

  it("permite limpiar provincia y comuna con sus botones de limpiar", () => {
    const handleProvinceChange = vi.fn();
    const handleCommuneChange = vi.fn();

    render(
      <SearchFilters
        regions={["Metropolitana de Santiago"]}
        onRegionsChange={vi.fn()}
        provinceId={51}
        onProvinceChange={handleProvinceChange}
        communeId={295}
        onCommuneChange={handleCommuneChange}
        availability={null}
        onAvailabilityChange={vi.fn()}
        onAmountRangeChange={vi.fn()}
        onClearFilters={vi.fn()}
        hasActiveFilters={true}
        provinces={mockProvinces}
        communes={mockCommunes}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /filtros avanzados/i }));

    const clearProvinceButton = screen.getByRole("button", { name: /limpiar provincia/i });
    fireEvent.click(clearProvinceButton);
    expect(handleProvinceChange).toHaveBeenCalledWith(undefined);
    expect(handleCommuneChange).toHaveBeenCalledWith(undefined);

    const clearCommuneButton = screen.getByRole("button", { name: /limpiar comuna/i });
    fireEvent.click(clearCommuneButton);
    expect(handleCommuneChange).toHaveBeenCalledWith(undefined);
  });
});
