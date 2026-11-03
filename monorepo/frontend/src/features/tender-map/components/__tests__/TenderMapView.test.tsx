import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { CompanyState } from "@/features/company-profile/components/CompanyProvider";
import type { Supplier } from "@/features/company-profile/services/supplierService";
import { ApiError } from "@/features/shared/api/client";
import type { RegionCenter } from "../../data/regionCenters";
import { getTendersMap } from "../../services/tenderMapService";
import { buildTenderMapPoint, buildTenderMapResult } from "../../test-utils";
import type { TenderMapPoint } from "../../types";
import { TenderMapView } from "../TenderMapView";

vi.mock("../../services/tenderMapService", () => ({
  getTendersMap: vi.fn(),
}));

// jsdom no tiene canvas: el mapa real se prueba a mano. El doble deja ver qué
// recibe, que es lo que decide la vista.
vi.mock("../LazyTenderMap", () => ({
  LazyTenderMap: ({ center, points }: { center: RegionCenter; points: TenderMapPoint[] }) => (
    <div data-testid="mapa" data-lat={center.lat} data-zoom={center.zoom}>
      {points.length} marcadores
    </div>
  ),
}));

let companyState: CompanyState = { status: "loading" };

vi.mock("@/features/company-profile/components/CompanyProvider", () => ({
  useCompany: () => ({ company: companyState, setSupplier: vi.fn(), refresh: vi.fn() }),
}));

const mockGet = vi.mocked(getTendersMap);

function conEmpresa(regions: string[]): CompanyState {
  return { status: "with-company", supplier: { id: "s-1", regions } as unknown as Supplier };
}

beforeEach(() => {
  mockGet.mockResolvedValue(buildTenderMapResult());
});

afterEach(() => {
  vi.clearAllMocks();
  companyState = { status: "loading" };
});

describe("TenderMapView", () => {
  it("centra el mapa en la zona de la empresa y muestra sus marcadores", async () => {
    companyState = conEmpresa(["Metropolitana", "Los Lagos"]);
    mockGet.mockResolvedValue(
      buildTenderMapResult({
        region: "Metropolitana de Santiago",
        items: [buildTenderMapPoint({ id: "a" }), buildTenderMapPoint({ id: "b" })],
        total: 2,
      }),
    );

    render(<TenderMapView />);

    // El perfil dice "Metropolitana"; el backend recibe el nombre canónico.
    await waitFor(() => expect(mockGet).toHaveBeenCalledWith("Metropolitana de Santiago"));
    expect(await screen.findByText("2 marcadores")).toBeInTheDocument();
    expect(screen.getByTestId("mapa")).toHaveAttribute("data-lat", "-33.4489");
    expect(screen.getByLabelText("Zona")).toHaveValue("Metropolitana de Santiago");
  });

  it("sin zona en el perfil pide elegir una y enlaza al perfil", () => {
    companyState = conEmpresa([]);

    render(<TenderMapView />);

    expect(screen.getByText(/elige una zona para ver/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /completa tu zona/i })).toHaveAttribute(
      "href",
      "/empresa",
    );
    expect(mockGet).not.toHaveBeenCalled();
    expect(screen.queryByTestId("mapa")).not.toBeInTheDocument();
  });

  it("si no se pudo cargar la empresa no la manda al perfil", () => {
    companyState = { status: "error" };

    render(<TenderMapView />);

    expect(screen.getByText(/no pudimos cargar los datos de tu empresa/i)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /completa tu zona/i })).not.toBeInTheDocument();
  });

  it("sin empresa enlaza a crear el perfil", () => {
    companyState = { status: "without-company" };

    render(<TenderMapView />);

    expect(screen.getByRole("link", { name: /completa tu zona/i })).toHaveAttribute(
      "href",
      "/perfil",
    );
  });

  it("al elegir una zona sin perfil, carga esa zona", async () => {
    companyState = conEmpresa([]);

    render(<TenderMapView />);
    fireEvent.change(screen.getByLabelText("Zona"), { target: { value: "Ñuble" } });

    await waitFor(() => expect(mockGet).toHaveBeenCalledWith("Ñuble"));
    expect(await screen.findByTestId("mapa")).toBeInTheDocument();
  });

  it("al cambiar de zona recentra el mapa y vuelve a pedir los marcadores", async () => {
    companyState = conEmpresa(["Los Lagos"]);

    render(<TenderMapView />);
    await screen.findByTestId("mapa");
    fireEvent.change(screen.getByLabelText("Zona"), {
      target: { value: "Aysén del General Carlos Ibáñez del Campo" },
    });

    await waitFor(() =>
      expect(mockGet).toHaveBeenLastCalledWith("Aysén del General Carlos Ibáñez del Campo"),
    );
    await waitFor(() =>
      expect(screen.getByTestId("mapa")).toHaveAttribute("data-lat", "-45.5712"),
    );
  });

  it("sin licitaciones con dirección en la zona lo dice y sugiere otra", async () => {
    companyState = conEmpresa(["Ñuble"]);
    mockGet.mockResolvedValue(buildTenderMapResult({ region: "Ñuble", items: [], total: 0 }));

    render(<TenderMapView />);

    expect(
      await screen.findByText(/no hay licitaciones con dirección de entrega en ñuble/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/prueba con otra zona/i)).toBeInTheDocument();
  });

  it("si falla la carga muestra el error y reintentar vuelve a pedir", async () => {
    companyState = conEmpresa(["Los Lagos"]);
    mockGet.mockRejectedValueOnce(new ApiError(503, "caída"));

    render(<TenderMapView />);

    expect(await screen.findByText("No se pudo cargar el mapa")).toBeInTheDocument();
    expect(screen.queryByTestId("mapa")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));

    expect(await screen.findByTestId("mapa")).toBeInTheDocument();
    expect(mockGet).toHaveBeenCalledTimes(2);
  });

  it("avisa cuando el tope deja marcadores fuera", async () => {
    companyState = conEmpresa(["Los Lagos"]);
    mockGet.mockResolvedValue(buildTenderMapResult({ total: 900, is_truncated: true }));

    render(<TenderMapView />);

    expect(await screen.findByText(/se muestran 1 de 900/i)).toBeInTheDocument();
  });
});
