import React from "react";
import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CreatingCompanyView } from "../CreatingCompanyView";

// Crear una empresa tarda entre 0,2 s y casi un minuto según esté despierto el
// proveedor de embeddings (medido en producción). Los mensajes acompañan esa
// espera para que un envío lento no parezca una pantalla colgada.
describe("CreatingCompanyView", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("anuncia la creación en curso apenas se muestra", () => {
    render(<CreatingCompanyView phase="creating" />);

    expect(screen.getByRole("status")).toHaveTextContent("Creando tu empresa…");
  });

  it("a los 4 segundos explica que está analizando el perfil", () => {
    render(<CreatingCompanyView phase="creating" />);

    act(() => {
      vi.advanceTimersByTime(3999);
    });
    expect(screen.getByRole("status")).toHaveTextContent("Creando tu empresa…");

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(screen.getByRole("status")).toHaveTextContent(
      "Analizando tu perfil para encontrar licitaciones compatibles…",
    );
  });

  it("a los 20 segundos avisa que está tardando más de lo normal", () => {
    render(<CreatingCompanyView phase="creating" />);

    act(() => {
      vi.advanceTimersByTime(20_000);
    });

    expect(screen.getByRole("status")).toHaveTextContent(
      "Está tardando más de lo normal. Seguimos trabajando, no cierres esta página.",
    );
  });

  it("en la fase de verificación dice que está confirmando el registro", () => {
    render(<CreatingCompanyView phase="verifying" />);

    expect(screen.getByRole("status")).toHaveTextContent(
      "Confirmando que tu empresa quedó registrada…",
    );
  });
});
