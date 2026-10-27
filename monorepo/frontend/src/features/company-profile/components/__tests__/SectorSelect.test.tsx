import React, { useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { SectorSelect } from "../SectorSelect";

const TECH = "Tecnologías de la información, telecomunicaciones y radiodifusión";
const CLEANING_SERVICE = "Servicios de limpieza industrial";
const CLEANING_GOODS = "Equipos y suministros de limpieza";
const CONSULTING = "Consultoria";
const FOOD = "Alimentos, bebidas y tabaco";

function sectorButtons() {
  return screen.getAllByRole("button").map((button) => button.textContent);
}

function Controlled({
  initial = [],
  onChange,
}: {
  initial?: string[];
  onChange: (selected: string[]) => void;
}) {
  const [selected, setSelected] = useState<string[]>(initial);
  return (
    <SectorSelect
      selected={selected}
      onChange={(next) => {
        setSelected(next);
        onChange(next);
      }}
    />
  );
}

describe("SectorSelect", () => {
  it("muestra los tres grupos con su título", () => {
    render(<SectorSelect selected={[]} onChange={vi.fn()} />);

    expect(screen.getByText("Servicios")).toBeInTheDocument();
    expect(screen.getByText("Bienes")).toBeInTheDocument();
    expect(screen.getByText("Obras y otros")).toBeInTheDocument();
  });

  it("al escribir 'limpieza' deja visibles solo los rubros que la contienen", async () => {
    render(<SectorSelect selected={[]} onChange={vi.fn()} />);

    await userEvent.type(screen.getByPlaceholderText("Buscar rubro"), "limpieza");

    expect(sectorButtons()).toEqual([CLEANING_SERVICE, CLEANING_GOODS]);
  });

  it("encuentra un rubro con tilde aunque el filtro no la lleve", async () => {
    render(<SectorSelect selected={[]} onChange={vi.fn()} />);

    await userEvent.type(screen.getByPlaceholderText("Buscar rubro"), "TECNOLOGIA");

    expect(screen.getByRole("button", { name: TECH })).toBeInTheDocument();
  });

  it("un rubro elegido sigue visible aunque el filtro no lo incluya", async () => {
    render(<SectorSelect selected={[FOOD]} onChange={vi.fn()} />);

    await userEvent.type(screen.getByPlaceholderText("Buscar rubro"), "limpieza");

    expect(screen.getByRole("button", { name: FOOD })).toHaveAttribute("aria-pressed", "true");
    expect(sectorButtons()).toEqual([CLEANING_SERVICE, FOOD, CLEANING_GOODS]);
  });

  it("elegir un rubro en Servicios y otro en Bienes conserva los dos en el orden elegido", async () => {
    const onChange = vi.fn();
    render(<Controlled onChange={onChange} />);

    await userEvent.click(screen.getByRole("button", { name: FOOD }));
    await userEvent.click(screen.getByRole("button", { name: CONSULTING }));

    expect(onChange).toHaveBeenLastCalledWith([FOOD, CONSULTING]);
  });

  it("quitar un rubro llama a onChange sin él", async () => {
    const onChange = vi.fn();
    render(<SectorSelect selected={[CONSULTING, FOOD]} onChange={onChange} />);

    await userEvent.click(screen.getByRole("button", { name: CONSULTING }));

    expect(onChange).toHaveBeenCalledWith([FOOD]);
  });
});
