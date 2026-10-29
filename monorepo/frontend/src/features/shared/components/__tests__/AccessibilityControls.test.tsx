import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import {
  PreferencesProvider,
  THEME_STORAGE_KEY,
  FONT_SCALE_STORAGE_KEY,
} from "@/features/shared/context/PreferencesContext";
import { AccessibilityControls } from "../AccessibilityControls";

function renderWithPreferences(ui: React.ReactElement) {
  return render(<PreferencesProvider>{ui}</PreferencesProvider>);
}

describe("AccessibilityControls", () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.className = "";
    document.documentElement.removeAttribute("data-theme");
    document.documentElement.removeAttribute("data-font-scale");
    document.documentElement.style.fontSize = "";
  });

  afterEach(() => {
    window.localStorage.clear();
    document.documentElement.className = "";
    document.documentElement.removeAttribute("data-theme");
    document.documentElement.removeAttribute("data-font-scale");
    document.documentElement.style.fontSize = "";
  });

  describe("Modo Oscuro (CA 1)", () => {
    it("alterna la clase .dark y el atributo data-theme en <html> al hacer clic en el botón", () => {
      renderWithPreferences(<AccessibilityControls />);

      const toggleButton = screen.getByTestId("theme-toggle");

      // Estado inicial en modo claro
      expect(document.documentElement.classList.contains("dark")).toBe(false);
      expect(document.documentElement.getAttribute("data-theme")).toBe("light");
      expect(toggleButton).toHaveAttribute("aria-pressed", "false");
      expect(toggleButton).toHaveAttribute("aria-label", "Cambiar a modo oscuro");

      // Clic para alternar a modo oscuro
      fireEvent.click(toggleButton);

      expect(document.documentElement.classList.contains("dark")).toBe(true);
      expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
      expect(toggleButton).toHaveAttribute("aria-pressed", "true");
      expect(toggleButton).toHaveAttribute("aria-label", "Cambiar a modo claro");
      expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");

      // Clic para volver a modo claro
      fireEvent.click(toggleButton);

      expect(document.documentElement.classList.contains("dark")).toBe(false);
      expect(document.documentElement.getAttribute("data-theme")).toBe("light");
      expect(toggleButton).toHaveAttribute("aria-pressed", "false");
      expect(toggleButton).toHaveAttribute("aria-label", "Cambiar a modo oscuro");
      expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
    });
  });

  describe("Escalado de Texto Proporcional (CA 2)", () => {
    it("cambia data-font-scale y font-size en <html> a 'normal', 'large' y 'xlarge'", () => {
      renderWithPreferences(<AccessibilityControls />);

      const normalBtn = screen.getByTestId("font-scale-normal");
      const largeBtn = screen.getByTestId("font-scale-large");
      const xlargeBtn = screen.getByTestId("font-scale-xlarge");

      // Estado inicial (normal = 100%)
      expect(document.documentElement.getAttribute("data-font-scale")).toBe("normal");
      expect(document.documentElement.style.fontSize).toBe("100%");
      expect(normalBtn).toHaveAttribute("aria-pressed", "true");
      expect(largeBtn).toHaveAttribute("aria-pressed", "false");
      expect(xlargeBtn).toHaveAttribute("aria-pressed", "false");

      // Clic en Grande (large = 112.5%)
      fireEvent.click(largeBtn);

      expect(document.documentElement.getAttribute("data-font-scale")).toBe("large");
      expect(document.documentElement.style.fontSize).toBe("112.5%");
      expect(largeBtn).toHaveAttribute("aria-pressed", "true");
      expect(normalBtn).toHaveAttribute("aria-pressed", "false");
      expect(window.localStorage.getItem(FONT_SCALE_STORAGE_KEY)).toBe("large");

      // Clic en Extra grande (xlarge = 125%)
      fireEvent.click(xlargeBtn);

      expect(document.documentElement.getAttribute("data-font-scale")).toBe("xlarge");
      expect(document.documentElement.style.fontSize).toBe("125%");
      expect(xlargeBtn).toHaveAttribute("aria-pressed", "true");
      expect(largeBtn).toHaveAttribute("aria-pressed", "false");
      expect(window.localStorage.getItem(FONT_SCALE_STORAGE_KEY)).toBe("xlarge");

      // Clic de vuelta en Normal (normal = 100%)
      fireEvent.click(normalBtn);

      expect(document.documentElement.getAttribute("data-font-scale")).toBe("normal");
      expect(document.documentElement.style.fontSize).toBe("100%");
      expect(normalBtn).toHaveAttribute("aria-pressed", "true");
      expect(xlargeBtn).toHaveAttribute("aria-pressed", "false");
      expect(window.localStorage.getItem(FONT_SCALE_STORAGE_KEY)).toBe("normal");
    });
  });

  describe("Variante compacta", () => {
    it("oculta las etiquetas de texto de tema cuando compact es true", () => {
      const { rerender } = renderWithPreferences(<AccessibilityControls compact={false} />);
      expect(screen.getByText("Oscuro")).toBeInTheDocument();

      rerender(
        <PreferencesProvider>
          <AccessibilityControls compact={true} />
        </PreferencesProvider>,
      );
      expect(screen.queryByText("Oscuro")).not.toBeInTheDocument();
    });
  });
});
