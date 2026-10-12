import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/features/shared/api/client";
import * as service from "../../services/sharingService";
import type { SharedTender } from "../../types";
import { SharedTenderView } from "../SharedTenderView";

const replace = vi.fn();
// Estable entre renders, como el router real de Next.
const router = { replace, push: vi.fn() };

vi.mock("next/navigation", () => ({
  useRouter: () => router,
}));

vi.mock("../../services/sharingService", () => ({
  getSharedTender: vi.fn(),
}));

function compartida(overrides: Partial<SharedTender> = {}): SharedTender {
  return {
    code: "1057539-228-COT26",
    name: "Mantención de áreas verdes",
    description: "Corte de pasto y poda en plazas.",
    status_code: "publicada",
    is_closed: false,
    published_at: "2026-09-26T15:00:00Z",
    closing_at: "2026-10-08T15:00:00Z",
    buyer_name: "Municipalidad de Providencia",
    buyer_unit: "Operaciones",
    region: "Metropolitana",
    commune: "Providencia",
    available_amount_clp: 5_000_000,
    items: [
      { name: "Corte de pasto", description: null, quantity: 12, unit_of_measure: "Servicio" },
    ],
    supplier_name: "Constructora Andes",
    score_pct: 84,
    analysis: {
      compatibility_score: 84,
      recommendation: "Postular",
      justification: "El rubro coincide con la experiencia declarada.",
      updated_at: "2026-09-27T15:00:00Z",
    },
    expires_at: "2026-10-05T15:00:00Z",
    ...overrides,
  };
}

describe("SharedTenderView", () => {
  beforeEach(() => {
    replace.mockReset();
    vi.mocked(service.getSharedTender).mockReset();
  });

  it("muestra el detalle, el análisis y la justificación sin sesión", async () => {
    // Criterio 2: se renderiza sin AuthProvider ni WorkspaceProvider.
    vi.mocked(service.getSharedTender).mockResolvedValue(compartida());

    render(<SharedTenderView token="tok" />);

    expect(
      await screen.findByRole("heading", { name: "Mantención de áreas verdes" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Municipalidad de Providencia/)).toBeInTheDocument();
    expect(screen.getByText(/\$5\.000\.000/)).toBeInTheDocument();
    expect(screen.getByText("Postular")).toBeInTheDocument();
    expect(
      screen.getByText("El rubro coincide con la experiencia declarada."),
    ).toBeInTheDocument();
    expect(screen.getByText(/compartido por constructora andes/i)).toBeInTheDocument();
    expect(service.getSharedTender).toHaveBeenCalledWith("tok");
  });

  it("lista los ítems de la licitación", async () => {
    vi.mocked(service.getSharedTender).mockResolvedValue(compartida());

    render(<SharedTenderView token="tok" />);

    const items = await screen.findByRole("list", { name: /ítems/i });
    expect(within(items).getByText("Corte de pasto")).toBeInTheDocument();
    expect(within(items).getByText(/12 Servicio/)).toBeInTheDocument();
  });

  it("indica hasta cuándo es válido el enlace", async () => {
    vi.mocked(service.getSharedTender).mockResolvedValue(compartida());

    render(<SharedTenderView token="tok" />);

    expect(await screen.findByText(/válido hasta el 05 oct 2026, 12:00/i)).toBeInTheDocument();
  });

  it("sin análisis lo explica en vez de mostrar un puntaje vacío", async () => {
    vi.mocked(service.getSharedTender).mockResolvedValue(
      compartida({ analysis: null, score_pct: null }),
    );

    render(<SharedTenderView token="tok" />);

    expect(
      await screen.findByText(/todavía no hay un análisis de compatibilidad/i),
    ).toBeInTheDocument();
    expect(screen.queryByText("Postular")).not.toBeInTheDocument();
  });

  it("avisa cuando la licitación ya cerró", async () => {
    vi.mocked(service.getSharedTender).mockResolvedValue(compartida({ is_closed: true }));

    render(<SharedTenderView token="tok" />);

    expect(await screen.findByText("Cerrada")).toBeInTheDocument();
  });

  it("un enlace caducado lleva a la página de enlace caducado", async () => {
    // Criterio 6.
    vi.mocked(service.getSharedTender).mockRejectedValue(
      new ApiError(410, "El enlace caducó.", "share_link_expired"),
    );

    render(<SharedTenderView token="tok" />);

    await vi.waitFor(() =>
      expect(replace).toHaveBeenCalledWith("/enlace-caducado?motivo=caducado"),
    );
  });

  it("un enlace revocado también, con su motivo", async () => {
    // Criterio 7.
    vi.mocked(service.getSharedTender).mockRejectedValue(
      new ApiError(410, "El enlace fue revocado.", "share_link_revoked"),
    );

    render(<SharedTenderView token="tok" />);

    await vi.waitFor(() =>
      expect(replace).toHaveBeenCalledWith("/enlace-caducado?motivo=revocado"),
    );
  });

  it("un enlace inexistente lo dice sin redirigir", async () => {
    vi.mocked(service.getSharedTender).mockRejectedValue(
      new ApiError(404, "El enlace no existe."),
    );

    render(<SharedTenderView token="tok" />);

    expect(await screen.findByRole("heading", { name: /enlace no válido/i })).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("si el servidor falla permite reintentar", async () => {
    const user = userEvent.setup();
    vi.mocked(service.getSharedTender)
      .mockRejectedValueOnce(new ApiError(500, "Error del servidor"))
      .mockResolvedValueOnce(compartida());

    render(<SharedTenderView token="tok" />);

    await user.click(await screen.findByRole("button", { name: /reintentar/i }));

    expect(
      await screen.findByRole("heading", { name: "Mantención de áreas verdes" }),
    ).toBeInTheDocument();
  });
});
