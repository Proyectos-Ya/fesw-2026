import { beforeEach, describe, expect, it, vi } from "vitest";
import { PostulationPackagePayload } from "../../types/schemas";
import { PostulationPanel } from "../postulation-panel";

describe("PostulationPanel (Shadow DOM UI)", () => {
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
    observations: "Obs",
    validity_days: 30,
    delivery_term_days: 5,
    files: [
      {
        name: "anexo_tecnico.docx",
        type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size: 1024,
        data_base64: "UEsDBBQAAAA=",
      },
    ],
  };

  beforeEach(() => {
    document.body.innerHTML = '<div id="test-container"></div>';
  });

  it("crea un contenedor con Shadow DOM y renderiza métricas sin innerHTML", () => {
    const onClearHighlight = vi.fn();
    const panel = new PostulationPanel({
      doc: document,
      onClearHighlight,
    });

    panel.render({
      packageData: samplePackage,
      filledCount: 3,
      incompleteCount: 1,
    });

    const host = document.getElementById("chiripa-postulation-panel-host");
    expect(host).not.toBeNull();
    expect(host?.shadowRoot).not.toBeNull();

    // Comprobar que en el shadowRoot aparecen los textos correctos
    const shadowText = host?.shadowRoot?.textContent ?? "";
    expect(shadowText).toContain("Chiripa — Postulación Asistida");
    expect(shadowText).toContain("2499-12-L126");
    expect(shadowText).toContain("3 completados");
    expect(shadowText).toContain("1 pendiente");
    expect(shadowText).toContain("enviar la oferta manualmente");
  });

  it("ejecuta callback onClearHighlight al hacer clic en el botón limpiar", () => {
    const onClearHighlight = vi.fn();
    const panel = new PostulationPanel({
      doc: document,
      onClearHighlight,
    });

    panel.render({
      packageData: samplePackage,
      filledCount: 2,
      incompleteCount: 0,
    });

    const host = document.getElementById("chiripa-postulation-panel-host");
    const clearBtn = host?.shadowRoot?.querySelector("#btnChiripaClearHighlight") as HTMLButtonElement | null;
    expect(clearBtn).not.toBeNull();

    clearBtn?.click();
    expect(onClearHighlight).toHaveBeenCalled();
  });

  it("permite desmontar el panel completamente", () => {
    const panel = new PostulationPanel({ doc: document });
    panel.render({
      packageData: samplePackage,
      filledCount: 1,
      incompleteCount: 0,
    });

    panel.destroy();
    expect(document.getElementById("chiripa-postulation-panel-host")).toBeNull();
  });

  it("CA7: lista los campos pendientes y muestra avisos como texto", () => {
    const panel = new PostulationPanel({ doc: document });
    panel.render({
      packageData: samplePackage,
      filledCount: 2,
      incompleteCount: 2,
      pending: ["Despacho", "<img src=x onerror=alert(1)>"],
      notice: "No pudimos verificar la empresa.",
    });
    const shadow = document.getElementById("chiripa-postulation-panel-host")!.shadowRoot!;
    const items = Array.from(shadow.querySelectorAll(".pending-list li")).map((li) => li.textContent);
    expect(items).toEqual(["Despacho", "<img src=x onerror=alert(1)>"]);
    expect(shadow.querySelector("img")).toBeNull();
    expect(shadow.querySelector(".notice")?.textContent).toBe("No pudimos verificar la empresa.");
  });
});
