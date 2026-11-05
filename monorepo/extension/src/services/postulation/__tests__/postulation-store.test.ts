import "fake-indexeddb/auto";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PostulationPackagePayload } from "../../../types/schemas";
import { PostulationStore } from "../postulation-store";

describe("PostulationStore", () => {
  const samplePackage: PostulationPackagePayload = {
    tender_code: "2499-12-L126",
    tender_title: "Adquisición de Insumos Médicos",
    company_rut: "76.086.428-5",
    company_name: "Inversiones Médicas SpA",
    items: [
      {
        line_number: 1,
        name: "Guantes",
        quantity: 10,
        unit_price: 1000,
        total_price: 10000,
      },
    ],
    total_clp: 10000,
    observations: "Observación de prueba",
    validity_days: 30,
    delivery_term_days: 5,
    files: [
      {
        name: "oferta.docx",
        type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size: 50,
        data_base64: "UEsDBBQAAAA=",
      },
    ],
  };

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("guarda y recupera un paquete de postulación antes de que expire", async () => {
    const store = new PostulationStore();
    await store.savePackage(samplePackage);

    const retrieved = await store.getPackage("2499-12-L126");
    expect(retrieved).not.toBeNull();
    expect(retrieved?.tender_code).toBe("2499-12-L126");
    expect(retrieved?.items.length).toBe(1);
    expect(retrieved?.files.length).toBe(1);
    expect(retrieved?.files[0].name).toBe("oferta.docx");
  });

  it("elimina y retorna null si el paquete ha superado su TTL (30 min)", async () => {
    const store = new PostulationStore();
    // Guardar con TTL de -1ms para que esté inmediatamente expirado
    await store.savePackage(samplePackage, -1000);

    const retrieved = await store.getPackage("2499-12-L126");
    expect(retrieved).toBeNull();
  });

  it("permite borrar manualmente un paquete ya utilizado o cancelado", async () => {
    const store = new PostulationStore();
    await store.savePackage(samplePackage);

    await store.clearPackage("2499-12-L126");
    const retrieved = await store.getPackage("2499-12-L126");
    expect(retrieved).toBeNull();
  });
});
