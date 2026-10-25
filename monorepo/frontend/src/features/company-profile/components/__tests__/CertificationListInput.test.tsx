import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { CertificationListInput } from "../CertificationListInput";
import type { CertificationEntry } from "../../profileSchema";

function renderInput(value: CertificationEntry[] = [], error?: string) {
  const onChange = vi.fn();
  render(
    <CertificationListInput
      label="Certificaciones relevantes"
      value={value}
      onChange={onChange}
      error={error}
    />,
  );
  return { onChange };
}

describe("CertificationListInput", () => {
  it("agrega una certificación solo con nombre", async () => {
    const { onChange } = renderInput();

    await userEvent.type(screen.getByLabelText("Nombre de la certificación"), "ISO 9001");
    await userEvent.click(screen.getByRole("button", { name: "Agregar" }));

    expect(onChange).toHaveBeenCalledWith([{ name: "ISO 9001", expires_at: null }]);
  });

  it("agrega una certificación con fecha de vencimiento", async () => {
    const { onChange } = renderInput();

    await userEvent.type(screen.getByLabelText("Nombre de la certificación"), "ISO 9001");
    await userEvent.type(screen.getByLabelText("Fecha de vencimiento"), "2026-12-31");
    await userEvent.click(screen.getByRole("button", { name: "Agregar" }));

    expect(onChange).toHaveBeenCalledWith([{ name: "ISO 9001", expires_at: "2026-12-31" }]);
  });

  it("agrega con Enter en el campo de nombre", async () => {
    const { onChange } = renderInput();

    await userEvent.type(screen.getByLabelText("Nombre de la certificación"), "SEC{Enter}");

    expect(onChange).toHaveBeenCalledWith([{ name: "SEC", expires_at: null }]);
  });

  it("limpia los campos después de agregar", async () => {
    renderInput();
    const name = screen.getByLabelText("Nombre de la certificación");
    const date = screen.getByLabelText("Fecha de vencimiento");

    await userEvent.type(name, "ISO 9001");
    await userEvent.type(date, "2026-12-31");
    await userEvent.click(screen.getByRole("button", { name: "Agregar" }));

    expect(name).toHaveValue("");
    expect(date).toHaveValue("");
  });

  it("no agrega nombres vacíos ni de solo espacios", async () => {
    const { onChange } = renderInput();

    await userEvent.click(screen.getByRole("button", { name: "Agregar" }));
    await userEvent.type(screen.getByLabelText("Nombre de la certificación"), "   {Enter}");

    expect(onChange).not.toHaveBeenCalled();
  });

  it("no agrega una certificación repetida", async () => {
    const { onChange } = renderInput(["ISO 9001"]);

    await userEvent.type(screen.getByLabelText("Nombre de la certificación"), "iso 9001{Enter}");

    expect(onChange).not.toHaveBeenCalled();
  });

  it("conserva las certificaciones existentes al agregar una nueva", async () => {
    const { onChange } = renderInput([{ name: "ISO 9001", expires_at: "2026-12-31" }, "SEC"]);

    await userEvent.type(screen.getByLabelText("Nombre de la certificación"), "OHSAS{Enter}");

    expect(onChange).toHaveBeenCalledWith([
      { name: "ISO 9001", expires_at: "2026-12-31" },
      { name: "SEC", expires_at: null },
      { name: "OHSAS", expires_at: null },
    ]);
  });

  it("muestra el nombre y la fecha formateada de cada certificación", () => {
    renderInput([{ name: "ISO 9001", expires_at: "2026-12-31" }, "SEC"]);

    expect(screen.getByText("ISO 9001")).toBeInTheDocument();
    expect(screen.getByText("Vence: 31/12/2026")).toBeInTheDocument();
    expect(screen.getByText("SEC")).toBeInTheDocument();
    expect(screen.getAllByText(/^Vence:/)).toHaveLength(1);
  });

  it("quita una certificación de la lista", async () => {
    const { onChange } = renderInput([{ name: "ISO 9001", expires_at: "2026-12-31" }, "SEC"]);

    await userEvent.click(screen.getByRole("button", { name: "Eliminar ISO 9001" }));

    expect(onChange).toHaveBeenCalledWith([{ name: "SEC", expires_at: null }]);
  });

  it("muestra el mensaje de error", () => {
    renderInput([], "Algo salió mal");

    expect(screen.getByText("Algo salió mal")).toBeInTheDocument();
  });
});
