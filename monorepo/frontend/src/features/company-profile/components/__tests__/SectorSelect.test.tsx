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
const GROUP_TITLES = [
  "Materias primas",
  "Maquinaria y equipamiento industrial",
  "Componentes y suministros",
  "Productos de uso final",
  "Servicios",
  "Obras y consultorías de ChileCompra",
];

// Solo los chips de rubro: las cabeceras de grupo no tienen aria-pressed.
function sectorButtons() {
  return screen
    .queryAllByRole("button")
    .filter((button) => button.hasAttribute("aria-pressed"))
    .map((button) => button.textContent);
}

// Las cabeceras de grupo son los botones con aria-expanded; un chip como
// "Servicios de limpieza industrial" también empieza con "Servicios".
function groupHeader(title: string) {
  const header = screen
    .getAllByRole("button")
    .find(
      (button) =>
        button.hasAttribute("aria-expanded") && button.textContent?.includes(`${title}(`),
    );
  if (!header) throw new Error(`No hay cabecera para el grupo ${title}`);
  return header;
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

    for (const title of GROUP_TITLES) {
      expect(screen.getByText(title)).toBeInTheDocument();
    }
  });

  it("los grupos empiezan plegados y no muestran rubros", () => {
    render(<SectorSelect selected={[]} onChange={vi.fn()} />);

    expect(sectorButtons()).toEqual([]);
    for (const title of GROUP_TITLES) {
      expect(groupHeader(title)).toHaveAttribute("aria-expanded", "false");
    }
  });

  it("la cabecera dice cuántos rubros tiene el grupo y cuántos están elegidos", () => {
    render(<SectorSelect selected={[CONSULTING, FOOD]} onChange={vi.fn()} />);

    expect(groupHeader("Servicios")).toHaveTextContent("(20)");
    expect(groupHeader("Obras y consultorías de ChileCompra")).toHaveTextContent("(3)");
    expect(groupHeader("Obras y consultorías de ChileCompra")).toHaveTextContent("1 elegido");
    expect(groupHeader("Productos de uso final")).toHaveTextContent("(15)");
    expect(groupHeader("Productos de uso final")).toHaveTextContent("1 elegido");
    expect(groupHeader("Materias primas")).toHaveTextContent("0 elegidos");
  });

  it("un clic en la cabecera despliega el grupo y otro lo pliega", async () => {
    render(<SectorSelect selected={[]} onChange={vi.fn()} />);

    await userEvent.click(groupHeader("Obras y consultorías de ChileCompra"));

    expect(groupHeader("Obras y consultorías de ChileCompra")).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    expect(sectorButtons()).toEqual([CONSULTING, "Obras", "Obras MINVU"]);

    await userEvent.click(groupHeader("Obras y consultorías de ChileCompra"));

    expect(sectorButtons()).toEqual([]);
  });

  it("al borrar la búsqueda los grupos vuelven a plegarse", async () => {
    render(<SectorSelect selected={[]} onChange={vi.fn()} />);
    const search = screen.getByPlaceholderText("Buscar rubro");

    await userEvent.type(search, "limpieza");
    expect(groupHeader("Servicios")).toHaveAttribute("aria-expanded", "true");

    await userEvent.clear(search);
    expect(sectorButtons()).toEqual([]);
  });

  it("al escribir 'limpieza' deja visibles solo los rubros que la contienen", async () => {
    render(<SectorSelect selected={[]} onChange={vi.fn()} />);

    await userEvent.type(screen.getByPlaceholderText("Buscar rubro"), "limpieza");

    expect(sectorButtons()).toEqual([CLEANING_GOODS, CLEANING_SERVICE]);
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
    expect(sectorButtons()).toEqual([CLEANING_GOODS, FOOD, CLEANING_SERVICE]);
  });

  it("elegir rubros en dos grupos conserva los dos en el orden elegido", async () => {
    const onChange = vi.fn();
    render(<Controlled onChange={onChange} />);
    await userEvent.click(groupHeader("Productos de uso final"));
    await userEvent.click(groupHeader("Obras y consultorías de ChileCompra"));

    await userEvent.click(screen.getByRole("button", { name: FOOD }));
    await userEvent.click(screen.getByRole("button", { name: CONSULTING }));

    expect(onChange).toHaveBeenLastCalledWith([FOOD, CONSULTING]);
  });

  it("quitar un rubro llama a onChange sin él", async () => {
    const onChange = vi.fn();
    render(<SectorSelect selected={[CONSULTING, FOOD]} onChange={onChange} />);
    await userEvent.click(groupHeader("Obras y consultorías de ChileCompra"));

    await userEvent.click(screen.getByRole("button", { name: CONSULTING }));

    expect(onChange).toHaveBeenCalledWith([FOOD]);
  });
});
