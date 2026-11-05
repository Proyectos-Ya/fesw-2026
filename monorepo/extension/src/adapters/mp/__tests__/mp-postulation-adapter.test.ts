import fs from "node:fs";
import path from "node:path";
import { beforeEach, describe, expect, it } from "vitest";
import { PostulationPackagePayload } from "../../../types/schemas";
import { MpPostulationAdapter } from "../mp-postulation-adapter";

describe("MpPostulationAdapter", () => {
  let loginHtml: string;
  let formHtml: string;

  beforeEach(() => {
    loginHtml = fs.readFileSync(
      path.resolve(__dirname, "../__fixtures__/login-page.html"),
      "utf-8"
    );
    formHtml = fs.readFileSync(
      path.resolve(__dirname, "../__fixtures__/postulation-form.html"),
      "utf-8"
    );
  });

  const samplePackage: PostulationPackagePayload = {
    tender_code: "2499-12-L126",
    tender_title: "Adquisición de Insumos Médicos",
    company_rut: "76.086.428-5",
    company_name: "Inversiones Médicas SpA",
    items: [
      {
        line_number: 1,
        name: "Guantes de Látex",
        quantity: 100,
        unit_price: 3500,
        total_price: 350000,
      },
    ],
    total_clp: 350000,
    observations: "Oferta formal de Chiripa.",
    validity_days: 30,
    delivery_term_days: 7,
    files: [
      {
        name: "propuesta_tecnica.docx",
        type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size: 100,
        data_base64: "UEsDBBQAAAA=",
      },
    ],
  };

  it("CA5: detecta página de login y no interactúa con credenciales", () => {
    document.documentElement.innerHTML = loginHtml;
    const adapter = new MpPostulationAdapter(document);

    expect(adapter.isLoginPage()).toBe(true);
    expect(adapter.isPostulationForm()).toBe(false);

    const state = adapter.detectState();
    expect(state.isLogin).toBe(true);
    expect(state.canPostulate).toBe(false);
  });

  it("CA6: detecta formulario de postulación y extrae código de licitación y RUT de sesión", () => {
    document.documentElement.innerHTML = formHtml;
    const adapter = new MpPostulationAdapter(document);

    expect(adapter.isLoginPage()).toBe(false);
    expect(adapter.isPostulationForm()).toBe(true);
    expect(adapter.extractTenderCode()).toBe("2499-12-L126");
    expect(adapter.extractSessionRut()).toBe("76.086.428-5");
  });

  it("CA6: rechaza autocompletar si el RUT de sesión no coincide con la empresa de Chiripa", () => {
    document.documentElement.innerHTML = formHtml;
    // Cambiar RUT en el DOM para simular otra sesión
    const rutEl = document.getElementById("lblUsuarioRUT");
    if (rutEl) rutEl.textContent = "12.345.678-9";

    const adapter = new MpPostulationAdapter(document);
    const result = adapter.fillPostulation(samplePackage);

    expect(result.success).toBe(false);
    expect(result.error).toBe("RUT_MISMATCH");

    // Verificar que los inputs quedaron intactos
    const precioInput = document.getElementById("txtPrecioUnitario_0") as HTMLInputElement;
    expect(precioInput.value).toBe("");
  });

  it("CA6 & CA7: llena valores de cotización, observaciones, plazos y resalta campos", () => {
    document.documentElement.innerHTML = formHtml;
    const adapter = new MpPostulationAdapter(document);

    const result = adapter.fillPostulation(samplePackage);

    expect(result.success).toBe(true);
    expect(result.filledCount).toBeGreaterThan(0);

    // Verificar precio del item 1
    const precioInput0 = document.getElementById("txtPrecioUnitario_0") as HTMLInputElement;
    expect(precioInput0.value).toBe("3500");
    expect(precioInput0.getAttribute("data-chiripa-field-status")).toBe("filled");

    // Verificar item 2 (no estaba en samplePackage, debe quedar incomplete)
    const precioInput1 = document.getElementById("txtPrecioUnitario_1") as HTMLInputElement;
    expect(precioInput1.getAttribute("data-chiripa-field-status")).toBe("incomplete");

    // Observaciones
    const obsTextarea = document.getElementById("txtObservaciones") as HTMLTextAreaElement;
    expect(obsTextarea.value).toBe("Oferta formal de Chiripa.");
    expect(obsTextarea.getAttribute("data-chiripa-field-status")).toBe("filled");

    // Plazos
    const validezInput = document.getElementById("txtValidezOferta") as HTMLInputElement;
    expect(validezInput.value).toBe("30");

    const plazoInput = document.getElementById("txtPlazoEntrega") as HTMLInputElement;
    expect(plazoInput.value).toBe("7");

    // CA8: Declaración jurada jamás debe ser marcada automáticamente
    const chkDeclaracion = document.getElementById("chkDeclaracionJurada") as HTMLInputElement;
    expect(chkDeclaracion.checked).toBe(false);
  });

  it("CA7: limpia los atributos de resaltado cuando se solicita", () => {
    document.documentElement.innerHTML = formHtml;
    const adapter = new MpPostulationAdapter(document);

    adapter.fillPostulation(samplePackage);
    adapter.clearHighlighting();

    const highlighted = document.querySelectorAll("[data-chiripa-field-status]");
    expect(highlighted.length).toBe(0);
  });
});
