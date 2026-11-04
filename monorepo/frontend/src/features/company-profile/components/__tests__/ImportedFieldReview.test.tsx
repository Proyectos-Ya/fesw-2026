import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ImportedFieldReview } from "../ImportedFieldReview";
import type { ReviewStatus } from "../../hooks/useProfileWizard";

function renderReview(status: ReviewStatus | undefined) {
  const handlers = { onConfirm: vi.fn(), onEdit: vi.fn(), onClear: vi.fn() };
  render(<ImportedFieldReview fieldLabel="regiones" status={status} {...handlers} />);
  return handlers;
}

describe("ImportedFieldReview", () => {
  it("no muestra nada si el campo no está en revisión", () => {
    renderReview(undefined);

    expect(screen.queryByText(/revis/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("pendiente: insignia de advertencia y botones Confirmar, Editar y Borrar", () => {
    const { onConfirm, onEdit, onClear } = renderReview("pending");

    expect(screen.getByText("Pendiente de revisión")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Confirmar regiones" }));
    fireEvent.click(screen.getByRole("button", { name: "Editar regiones" }));
    fireEvent.click(screen.getByRole("button", { name: "Borrar regiones" }));

    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onEdit).toHaveBeenCalledTimes(1);
    expect(onClear).toHaveBeenCalledTimes(1);
  });

  it("editando: sigue pendiente y ya no ofrece Editar", () => {
    renderReview("editing");

    expect(screen.getByText("Pendiente de revisión")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirmar regiones" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Borrar regiones" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Editar regiones" })).not.toBeInTheDocument();
  });

  it("confirmado: insignia Revisado, sin Confirmar", () => {
    renderReview("confirmed");

    expect(screen.getByText("Revisado")).toBeInTheDocument();
    expect(screen.queryByText("Pendiente de revisión")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Confirmar regiones" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Editar regiones" })).toBeInTheDocument();
  });
});
