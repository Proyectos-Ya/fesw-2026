import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ExtensionRequiredDialog } from "../ExtensionRequiredDialog";

describe("ExtensionRequiredDialog (CA2)", () => {
  it("muestra enlace a Chrome Web Store cuando el navegador es Chrome", () => {
    render(
      <ExtensionRequiredDialog
        open={true}
        onClose={vi.fn()}
        browser="chrome"
      />
    );

    expect(screen.getByText(/Necesitas la extensión de Chiripa/i)).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /Instalar extensión/i });
    expect(link).toHaveAttribute("href", expect.stringContaining("chromewebstore.google.com"));
  });

  it("muestra enlace a Firefox AMO cuando el navegador es Firefox", () => {
    render(
      <ExtensionRequiredDialog
        open={true}
        onClose={vi.fn()}
        browser="firefox"
      />
    );

    const link = screen.getByRole("link", { name: /Instalar extensión/i });
    expect(link).toHaveAttribute("href", expect.stringContaining("addons.mozilla.org"));
  });

  it("recarga la página cuando el usuario presiona 'Ya la instalé — Recargar'", () => {
    const reloadMock = vi.fn();
    Object.defineProperty(window, "location", {
      writable: true,
      value: { reload: reloadMock },
    });

    render(
      <ExtensionRequiredDialog
        open={true}
        onClose={vi.fn()}
        browser="chrome"
      />
    );

    const reloadBtn = screen.getByRole("button", { name: /Ya la instalé — Recargar/i });
    fireEvent.click(reloadBtn);
    expect(reloadMock).toHaveBeenCalled();
  });
});
