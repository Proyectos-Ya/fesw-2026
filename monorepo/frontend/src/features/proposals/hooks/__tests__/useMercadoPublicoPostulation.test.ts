import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as bridge from "@/features/shared/extension/extensionBridge";
import * as proposalService from "../../services/proposalService";
import type { PostulationPackage } from "../../types";
import { useMercadoPublicoPostulation } from "../useMercadoPublicoPostulation";

vi.mock("@/features/shared/extension/extensionBridge");
vi.mock("../../services/proposalService");

describe("useMercadoPublicoPostulation", () => {
  const samplePackage: PostulationPackage = {
    tender: {
      id: "t-1",
      code: "2499-12-L126",
      title: "Licitacion",
      closing_at: "2026-12-31T00:00:00Z",
      url: "https://mercadopublico.cl",
    },
    company: {
      rut: "76.086.428-5",
      name: "Empresa",
      contact_name: null,
      contact_email: null,
      contact_phone: null,
    },
    items: [],
    total_suggested_clp: 0,
    observations: "",
    validity_days: 30,
    delivery_term_days: 15,
    required_documents: [],
  };

  beforeEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
  });

  it("si la extensión no está instalada, abre ExtensionRequiredDialog (CA2)", async () => {
    vi.mocked(bridge.probeExtension).mockResolvedValue({ installed: false });

    const { result } = renderHook(() =>
      useMercadoPublicoPostulation({
        tenderId: "t-1",
        tenderCode: "2499-12-L126",
      })
    );

    await act(async () => {
      await result.current.startPostulation();
    });

    expect(result.current.showExtensionRequiredDialog).toBe(true);
    expect(result.current.showConfirmDialog).toBe(false);
  });

  it("si la extensión está instalada, abre pestaña inactiva en MP y abre PostulationConfirmDialog (CA3)", async () => {
    vi.mocked(bridge.probeExtension).mockResolvedValue({
      installed: true,
      version: "0.2.0",
      postulation_enabled: true,
      paired: true,
    });
    vi.mocked(bridge.openPostulationTab).mockResolvedValue({ ok: true, tab_id: 10 });
    vi.mocked(proposalService.getPostulationPackage).mockResolvedValue(samplePackage);

    const { result } = renderHook(() =>
      useMercadoPublicoPostulation({
        tenderId: "t-1",
        tenderCode: "2499-12-L126",
      })
    );

    await act(async () => {
      await result.current.startPostulation();
    });

    expect(bridge.openPostulationTab).toHaveBeenCalledWith(
      "2499-12-L126",
      "https://www.mercadopublico.cl/Portal/Modules/Menu/Menu.aspx"
    );
    expect(proposalService.getPostulationPackage).toHaveBeenCalledWith("t-1");
    expect(result.current.showConfirmDialog).toBe(true);
    expect(result.current.packageData).toEqual(samplePackage);
  });

  it("CA3: para una Compra Ágil abre directo la ficha de cotización", async () => {
    vi.mocked(bridge.probeExtension).mockResolvedValue({
      installed: true,
      version: "0.2.0",
      postulation_enabled: true,
      paired: true,
    });
    vi.mocked(bridge.openPostulationTab).mockResolvedValue({ ok: true, tab_id: 11 });
    vi.mocked(proposalService.getPostulationPackage).mockResolvedValue(samplePackage);

    const { result } = renderHook(() =>
      useMercadoPublicoPostulation({ tenderId: "t-2", tenderCode: "5626-943-COT26" })
    );

    await act(async () => {
      await result.current.startPostulation();
    });

    expect(bridge.openPostulationTab).toHaveBeenCalledWith(
      "5626-943-COT26",
      "https://compra-agil.mercadopublico.cl/resumen-cotizacion/5626-943-COT26"
    );
  });

  it("al confirmar postulación, envía payload al bridge y enfoca pestaña (CA4)", async () => {
    vi.mocked(bridge.confirmPostulation).mockResolvedValue({ ok: true });
    vi.mocked(bridge.focusPostulationTab).mockResolvedValue({ ok: true });

    const { result } = renderHook(() =>
      useMercadoPublicoPostulation({
        tenderId: "t-1",
        tenderCode: "2499-12-L126",
      })
    );

    const payload: bridge.PostulationConfirmPayload = {
      tender_code: "2499-12-L126",
      company_rut: "76.086.428-5",
      company_name: "Empresa",
      items: [],
      total_clp: 50000,
      observations: "Nota",
      validity_days: 30,
      delivery_term_days: 10,
      files: [],
    };

    await act(async () => {
      await result.current.confirm(payload);
    });

    expect(bridge.confirmPostulation).toHaveBeenCalledWith(payload);
    expect(bridge.focusPostulationTab).toHaveBeenCalledWith("2499-12-L126");
    expect(result.current.showConfirmDialog).toBe(false);
  });

  describe("vinculación automática", () => {
    const installedNotPaired = { installed: true, version: "0.2.0", postulation_enabled: true, paired: false };

    it("vincula sola si la extensión está instalada pero no vinculada, y sigue el flujo", async () => {
      vi.mocked(bridge.probeExtension).mockResolvedValue(installedNotPaired);
      vi.mocked(bridge.pairExtension).mockResolvedValue({ ok: true });
      vi.mocked(bridge.openPostulationTab).mockResolvedValue({ ok: true, tab_id: 12 });
      vi.mocked(proposalService.getPostulationPackage).mockResolvedValue(samplePackage);

      const { result } = renderHook(() =>
        useMercadoPublicoPostulation({ tenderId: "t-3", tenderCode: "5626-943-COT26" })
      );
      await act(async () => {
        await result.current.startPostulation();
      });

      expect(bridge.pairExtension).toHaveBeenCalledTimes(1);
      expect(bridge.openPostulationTab).toHaveBeenCalled();
      expect(result.current.pairingRequired).toBe(false);
      expect(result.current.showConfirmDialog).toBe(true);
    });

    it("si no logra vincular, pide vincular y no abre Mercado Público", async () => {
      vi.mocked(bridge.probeExtension).mockResolvedValue(installedNotPaired);
      vi.mocked(bridge.pairExtension).mockResolvedValue({ ok: false, error: "sin respuesta" });

      const { result } = renderHook(() =>
        useMercadoPublicoPostulation({ tenderId: "t-3", tenderCode: "5626-943-COT26" })
      );
      await act(async () => {
        await result.current.startPostulation();
      });

      expect(result.current.pairingRequired).toBe(true);
      expect(result.current.showConfirmDialog).toBe(false);
      expect(bridge.openPostulationTab).not.toHaveBeenCalled();
      expect(proposalService.getPostulationPackage).not.toHaveBeenCalled();
    });

    it("«Vincular» reintenta la vinculación y, si funciona, continúa", async () => {
      vi.mocked(bridge.probeExtension).mockResolvedValue(installedNotPaired);
      vi.mocked(bridge.pairExtension).mockResolvedValueOnce({ ok: false }).mockResolvedValueOnce({ ok: true });
      vi.mocked(bridge.openPostulationTab).mockResolvedValue({ ok: true, tab_id: 12 });
      vi.mocked(proposalService.getPostulationPackage).mockResolvedValue(samplePackage);

      const { result } = renderHook(() =>
        useMercadoPublicoPostulation({ tenderId: "t-3", tenderCode: "5626-943-COT26" })
      );
      await act(async () => {
        await result.current.startPostulation();
      });
      await act(async () => {
        await result.current.pairAndContinue();
      });

      expect(result.current.pairingRequired).toBe(false);
      expect(result.current.showConfirmDialog).toBe(true);
    });

    it("«Postular manualmente» abre la ficha de Mercado Público sin llenado", async () => {
      vi.mocked(bridge.probeExtension).mockResolvedValue(installedNotPaired);
      vi.mocked(bridge.pairExtension).mockResolvedValue({ ok: false });
      const open = vi.spyOn(window, "open").mockReturnValue(null);

      const { result } = renderHook(() =>
        useMercadoPublicoPostulation({ tenderId: "t-3", tenderCode: "5626-943-COT26" })
      );
      await act(async () => {
        await result.current.startPostulation();
      });
      act(() => result.current.postManually());

      expect(open).toHaveBeenCalledWith(
        "https://compra-agil.mercadopublico.cl/resumen-cotizacion/5626-943-COT26",
        "_blank",
        "noopener,noreferrer"
      );
      expect(result.current.pairingRequired).toBe(false);
      expect(bridge.confirmPostulation).not.toHaveBeenCalled();
    });
  });
});

