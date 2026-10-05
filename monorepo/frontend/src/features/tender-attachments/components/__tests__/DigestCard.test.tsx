import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/features/shared/api/client";
import { getTenderDigest } from "../../services/tenderDigestService";
import { buildDigestCitation, buildTenderDigest } from "../../test-utils";
import { AI_NOTICE } from "../../types";
import { DigestCard } from "../DigestCard";

vi.mock("../../services/tenderDigestService", () => ({
  getTenderDigest: vi.fn(),
}));

describe("DigestCard", () => {
  const baseDigest = buildTenderDigest();

  beforeEach(() => {
    vi.mocked(getTenderDigest).mockReset();
    vi.mocked(getTenderDigest).mockResolvedValue(baseDigest);
  });

  it("renderiza encabezado, aviso de IA y badge", async () => {
    render(<DigestCard tenderId="t-1" refreshKey="k-1" />);

    expect(await screen.findByText("Resumen de los anexos")).toBeInTheDocument();
    expect(screen.getByText("Generado con IA")).toBeInTheDocument();
    expect(screen.getByText(AI_NOTICE)).toBeInTheDocument();
  });

  it("renderiza discrepancias con tarjeta y referencia de Mercado Público", async () => {
    render(<DigestCard tenderId="t-1" refreshKey="k-1" />);

    expect(
      await screen.findByText("Discrepancia detectada: Cierre del primer llamado")
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("discrepancy-reference")
    ).toHaveTextContent("Mercado Público informa: 04-10-2026 15:00");
  });

  it("muestra presupuesto y fecha de cierre formateados", async () => {
    render(<DigestCard tenderId="t-1" refreshKey="k-1" />);

    expect(
      await screen.findByText("$5.000.000 (IVA incluido)")
    ).toBeInTheDocument();
    expect(screen.getByText("05-10-2026, 15:00")).toBeInTheDocument();
  });

  it("muestra mensaje de conflicto y alternativas cuando los anexos no coinciden", async () => {
    const cita = buildDigestCitation();
    const digestConConflicto = buildTenderDigest({
      data: {
        ...baseDigest.data,
        campos: {
          ...baseDigest.data.campos,
          fecha_cierre_primer_llamado: {
            valor: null,
            en_conflicto: true,
            alternativas: [
              { valor: { fecha: "2026-10-05", hora: "15:00" }, citas: [cita] },
              { valor: { fecha: "2026-10-06", hora: "15:00" }, citas: [cita] },
            ],
            citas: [cita],
          },
        },
      },
    });
    vi.mocked(getTenderDigest).mockResolvedValue(digestConConflicto);

    render(<DigestCard tenderId="t-1" refreshKey="k-1" />);

    expect(await screen.findByText("Los anexos no coinciden")).toBeInTheDocument();
    expect(screen.getByText("05-10-2026, 15:00")).toBeInTheDocument();
    expect(screen.getByText("06-10-2026, 15:00")).toBeInTheDocument();
  });

  it("muestra requisito obligatorio con badge", async () => {
    render(<DigestCard tenderId="t-1" refreshKey="k-1" />);

    expect(
      await screen.findByText("Certificación ISO 9001 vigente")
    ).toBeInTheDocument();
    expect(screen.getByText("Obligatorio")).toBeInTheDocument();
  });

  it("muestra fuentes analizadas con verificación y texto no disponible", async () => {
    const digestFuentes = buildTenderDigest({
      data: {
        ...baseDigest.data,
        fuentes: [
          {
            anexo_id: "a-1",
            archivo_id: "f-1",
            documento: "Bases.pdf",
            visibilidad: "shared",
            citas_total: 14,
            citas_verificadas: 12,
            texto_disponible: true,
            modelo: "gemini",
            prompt_version: "v1",
            procesado_en: "2026-10-04",
          },
          {
            anexo_id: "a-2",
            archivo_id: "f-2",
            documento: "Escaneado.pdf",
            visibilidad: "shared",
            citas_total: 0,
            citas_verificadas: 0,
            texto_disponible: false,
            modelo: "gemini",
            prompt_version: "v1",
            procesado_en: "2026-10-04",
          },
        ],
      },
    });
    vi.mocked(getTenderDigest).mockResolvedValue(digestFuentes);

    render(<DigestCard tenderId="t-1" refreshKey="k-1" />);

    expect(
      await screen.findByText("Bases.pdf: 12 de 14 citas verificadas")
    ).toBeInTheDocument();
    expect(
      screen.getByText("Escaneado.pdf: sin texto para verificar las citas")
    ).toBeInTheDocument();
  });

  it("muestra aviso de empresa cuando scope es workspace", async () => {
    const digestWorkspace = buildTenderDigest({ scope: "workspace" });
    vi.mocked(getTenderDigest).mockResolvedValue(digestWorkspace);

    render(<DigestCard tenderId="t-1" refreshKey="k-1" />);

    expect(
      await screen.findByText("Incluye anexos que solo ve tu empresa.")
    ).toBeInTheDocument();
  });

  it("muestra mensaje de vacío cuando status es empty", async () => {
    const digestVacio = buildTenderDigest({ status: "empty" });
    vi.mocked(getTenderDigest).mockResolvedValue(digestVacio);

    render(<DigestCard tenderId="t-1" refreshKey="k-1" />);

    expect(
      await screen.findByText("Todavía no hay anexos procesados para resumir.")
    ).toBeInTheDocument();
  });

  it("muestra error con opción de reintentar", async () => {
    const user = userEvent.setup();
    vi.mocked(getTenderDigest).mockRejectedValueOnce(
      new ApiError(500, "Error en el servidor")
    );

    render(<DigestCard tenderId="t-1" refreshKey="k-1" />);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Error en el servidor")).toBeInTheDocument();

    vi.mocked(getTenderDigest).mockResolvedValue(baseDigest);
    await user.click(screen.getByRole("button", { name: "Reintentar" }));

    expect(await screen.findByText("Resumen de los anexos")).toBeInTheDocument();
    expect(getTenderDigest).toHaveBeenCalledTimes(2);
  });
});
