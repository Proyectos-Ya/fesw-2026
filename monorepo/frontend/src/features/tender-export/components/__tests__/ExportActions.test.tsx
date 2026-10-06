import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ExportState } from "../../hooks/useTenderExport";
import { ExportActions } from "../ExportActions";

const exportAs = vi.fn();
let estado: ExportState = { status: "idle" };

vi.mock("../../hooks/useTenderExport", () => ({
  useTenderExport: () => ({ state: estado, exportAs }),
}));

describe("ExportActions", () => {
  beforeEach(() => {
    exportAs.mockReset();
    estado = { status: "idle" };
  });

  it("Exportar a PDF lo pide de inmediato", async () => {
    // Criterio 3.
    const user = userEvent.setup();
    render(<ExportActions tenderId="t-1" />);

    await user.click(screen.getByRole("button", { name: /exportar a pdf/i }));

    expect(exportAs).toHaveBeenCalledWith("pdf", []);
  });

  it("Exportar a Excel primero deja elegir las secciones", async () => {
    // Criterios 4 y 5.
    const user = userEvent.setup();
    render(<ExportActions tenderId="t-1" />);

    await user.click(screen.getByRole("button", { name: /exportar a excel/i }));
    expect(exportAs).not.toHaveBeenCalled();
    await user.click(screen.getByRole("switch", { name: /análisis de la ia/i }));
    await user.click(screen.getByRole("button", { name: /generar excel/i }));

    expect(exportAs).toHaveBeenCalledWith("xlsx", ["datos_generales", "montos", "items", "hitos"]);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("mientras genera deshabilita los botones y dice qué genera", () => {
    estado = { status: "generating", format: "xlsx" };

    render(<ExportActions tenderId="t-1" />);

    expect(screen.getByRole("button", { name: /generando excel/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /exportar a pdf/i })).toBeDisabled();
  });

  it("si pasó a segundo plano muestra el aviso del correo", () => {
    // Criterios 8 y 9.
    estado = {
      status: "queued",
      format: "pdf",
      message:
        "Tu archivo se está generando en segundo plano. Te avisaremos por correo cuando esté listo para descargar.",
    };

    render(<ExportActions tenderId="t-1" />);

    expect(screen.getByRole("status")).toHaveTextContent(/te avisaremos por correo/i);
  });

  it("al terminar confirma la descarga", () => {
    estado = { status: "done", format: "pdf" };

    render(<ExportActions tenderId="t-1" />);

    expect(screen.getByRole("status")).toHaveTextContent(/tu pdf está listo/i);
  });

  it("un error se muestra como alerta", () => {
    estado = { status: "error", message: "No se pudo generar el archivo." };

    render(<ExportActions tenderId="t-1" />);

    expect(screen.getByRole("alert")).toHaveTextContent("No se pudo generar el archivo.");
  });
});
