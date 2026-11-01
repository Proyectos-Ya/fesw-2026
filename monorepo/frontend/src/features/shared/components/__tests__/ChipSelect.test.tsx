import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ChipSelect } from "../ChipSelect";

const OPTIONS = ["Norte", "Centro", "Sur"];

describe("ChipSelect", () => {
  it("agrega y quita opciones al hacer clic", () => {
    const onChange = vi.fn();
    render(
      <ChipSelect label="Zonas" options={OPTIONS} selected={["Norte"]} onChange={onChange} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Centro" }));
    fireEvent.click(screen.getByRole("button", { name: "Norte" }));

    expect(onChange).toHaveBeenNthCalledWith(1, ["Norte", "Centro"]);
    expect(onChange).toHaveBeenNthCalledWith(2, []);
  });

  it("con disabled un clic no cambia la selección", () => {
    const onChange = vi.fn();
    render(
      <ChipSelect
        label="Zonas"
        options={OPTIONS}
        selected={["Norte"]}
        onChange={onChange}
        disabled
      />,
    );

    const centro = screen.getByRole("button", { name: "Centro" });
    fireEvent.click(centro);

    expect(centro).toBeDisabled();
    expect(onChange).not.toHaveBeenCalled();
  });

  it("con disabled sigue mostrando qué opciones están marcadas", () => {
    render(
      <ChipSelect
        label="Zonas"
        options={OPTIONS}
        selected={["Norte"]}
        onChange={vi.fn()}
        disabled
      />,
    );

    expect(screen.getByRole("button", { name: "Norte" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Sur" })).toHaveAttribute("aria-pressed", "false");
  });
});
