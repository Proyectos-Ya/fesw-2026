import "fake-indexeddb/auto";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PostulationPackagePayload } from "../../../types/schemas";
import { PostulationCoordinator } from "../postulation-coordinator";
import { PostulationStore } from "../postulation-store";

describe("PostulationCoordinator", () => {
  let mockTabsCreate: ReturnType<typeof vi.fn>;
  let mockTabsUpdate: ReturnType<typeof vi.fn>;
  let mockTabsSendMessage: ReturnType<typeof vi.fn>;
  let store: PostulationStore;

  const samplePackage: PostulationPackagePayload = {
    tender_code: "2499-12-L126",
    company_rut: "76.086.428-5",
    company_name: "Test SpA",
    items: [
      {
        line_number: 1,
        name: "Item 1",
        quantity: 1,
        unit_price: 500,
        total_price: 500,
      },
    ],
    total_clp: 500,
    observations: "Obs",
    validity_days: 30,
    delivery_term_days: 10,
    files: [],
  };

  beforeEach(() => {
    mockTabsCreate = vi.fn().mockResolvedValue({ id: 99, windowId: 1 });
    mockTabsUpdate = vi.fn().mockResolvedValue({ id: 99, active: true });
    mockTabsSendMessage = vi.fn().mockResolvedValue({ ack: true });
    store = new PostulationStore();
  });

  it("abre pestaña de Mercado Público inactiva (active: false) con la URL de la licitación", async () => {
    const coordinator = new PostulationCoordinator({
      store,
      tabsCreate: mockTabsCreate,
      tabsUpdate: mockTabsUpdate,
      tabsSendMessage: mockTabsSendMessage,
    });

    const res = await coordinator.openPostulationTab("2499-12-L126", "https://mercadopublico.cl/ficha.html?code=2499-12-L126");

    expect(res.ok).toBe(true);
    expect(res.tab_id).toBe(99);
    expect(mockTabsCreate).toHaveBeenCalledWith({
      url: "https://mercadopublico.cl/ficha.html?code=2499-12-L126",
      active: false,
    });
  });

  it("confirma postulación, guarda paquete en almacén y enfoca la pestaña", async () => {
    const coordinator = new PostulationCoordinator({
      store,
      tabsCreate: mockTabsCreate,
      tabsUpdate: mockTabsUpdate,
      tabsSendMessage: mockTabsSendMessage,
    });

    // 1. Abre pestaña primero para registrar tabId
    await coordinator.openPostulationTab("2499-12-L126");

    // 2. Confirma postulación
    const res = await coordinator.confirmPostulation(samplePackage);
    expect(res.ok).toBe(true);

    // Debe enfocar la pestaña
    expect(mockTabsUpdate).toHaveBeenCalledWith(99, { active: true });

    // Debe persistir en store
    const stored = await store.getPackage("2499-12-L126");
    expect(stored).not.toBeNull();
    expect(stored?.tender_code).toBe("2499-12-L126");
  });

  it("entrega paquete pendiente a la pestaña de Mercado Público", async () => {
    const coordinator = new PostulationCoordinator({
      store,
      tabsCreate: mockTabsCreate,
      tabsUpdate: mockTabsUpdate,
      tabsSendMessage: mockTabsSendMessage,
    });

    await store.savePackage(samplePackage);

    const pending = await coordinator.getPendingPackage("2499-12-L126");
    expect(pending).not.toBeNull();
    expect(pending?.company_rut).toBe("76.086.428-5");
  });
});
