import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ExtensionRequiredDialog } from "../ExtensionRequiredDialog";

describe("ExtensionRequiredDialog (CA2)", () => {
  it("en Chrome ofrece primero el .zip de Chrome, con pasos y enlace al de Firefox", () => {
    render(<ExtensionRequiredDialog open={true} onClose={vi.fn()} browser="chrome" />);

    expect(screen.getByText(/Necesitas la extensión de Chiripa/i)).toBeInTheDocument();
    const main = screen.getByRole("link", { name: /Descargar extensión para Chrome/i });
    expect(main).toHaveAttribute("href", "/extension/chiripa-chrome.zip");
    expect(main).toHaveAttribute("download");
    expect(screen.getByRole("link", { name: /versión para Firefox/i })).toHaveAttribute(
      "href",
      "/extension/chiripa-firefox.zip"
    );
    expect(screen.getByText(/Cargar descomprimida/i)).toBeInTheDocument();
    expect(screen.getByText("chrome://extensions")).toBeInTheDocument();
  });

  it("en Firefox ofrece el .zip de Firefox y avisa que el complemento temporal se borra al cerrar", () => {
    render(<ExtensionRequiredDialog open={true} onClose={vi.fn()} browser="firefox" />);

    expect(screen.getByRole("link", { name: /Descargar extensión para Firefox/i })).toHaveAttribute(
      "href",
      "/extension/chiripa-firefox.zip"
    );
    expect(screen.getByText("about:debugging#/runtime/this-firefox")).toBeInTheDocument();
    expect(screen.getByText(/Cargar complemento temporal/i)).toBeInTheDocument();
    expect(screen.getByText(/se elimina al cerrar Firefox/i)).toBeInTheDocument();
  });

  it("copia la dirección de ajustes, que no se puede abrir desde un enlace", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    render(<ExtensionRequiredDialog open={true} onClose={vi.fn()} browser="chrome" />);

    fireEvent.click(screen.getByRole("button", { name: /Copiar chrome:\/\/extensions/i }));
    expect(writeText).toHaveBeenCalledWith("chrome://extensions");
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
