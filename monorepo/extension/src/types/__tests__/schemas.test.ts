import { describe, expect, it } from "vitest";
import {
  BridgeConfirmPostulationMessageSchema,
  BridgeFocusTabMessageSchema,
  BridgeOpenPostulationMessageSchema,
  PostulationPackagePayloadSchema,
} from "../schemas";

describe("Postulation Schemas", () => {
  it("valida payload de paquete de postulación correcto", () => {
    const valid = {
      tender_code: "2499-12-L126",
      tender_title: "Adquisición de Insumos Médicos",
      company_rut: "76.086.428-5",
      company_name: "Inversiones Médicas SpA",
      items: [
        {
          line_number: 1,
          name: "Guantes de Látex",
          quantity: 100,
          unit_price: 5000,
          total_price: 500000,
          technical_spec: "Caja x 100 unidades",
        },
      ],
      total_clp: 500000,
      observations: "Oferta conforme a bases administrativas y técnicas.",
      validity_days: 60,
      delivery_term_days: 10,
      files: [
        {
          name: "oferta_tecnica.docx",
          type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
          size: 1024,
          data_base64: "UEsDBBQAAAAIA...",
        },
      ],
    };

    const parsed = PostulationPackagePayloadSchema.safeParse(valid);
    expect(parsed.success).toBe(true);
  });

  it("rechaza payload con precios negativos o líneas inválidas", () => {
    const invalid = {
      tender_code: "",
      company_rut: "76.086.428-5",
      company_name: "Empresa",
      items: [
        {
          line_number: 0,
          name: "Item",
          quantity: -1,
          unit_price: -500,
          total_price: -500,
        },
      ],
      total_clp: -500,
    };

    const parsed = PostulationPackagePayloadSchema.safeParse(invalid);
    expect(parsed.success).toBe(false);
  });

  it("valida mensaje OPEN_POSTULATION del bridge", () => {
    const msg = {
      target: "CHIRIPA_EXTENSION",
      type: "OPEN_POSTULATION",
      nonce: "4f26b52f-1a98-4ca7-a1e4-d1952ee04c81",
      payload: {
        tender_code: "2499-12-L126",
        mp_url: "https://www.mercadopublico.cl/ficha.html?code=2499-12-L126",
      },
    };

    const parsed = BridgeOpenPostulationMessageSchema.safeParse(msg);
    expect(parsed.success).toBe(true);
  });

  it("valida mensaje CONFIRM_POSTULATION del bridge", () => {
    const msg = {
      target: "CHIRIPA_EXTENSION",
      type: "CONFIRM_POSTULATION",
      nonce: "b7e42d76-9d32-4299-8cfb-6f81a18ea72c",
      payload: {
        tender_code: "2499-12-L126",
        company_rut: "76.086.428-5",
        company_name: "Test SpA",
        items: [
          {
            line_number: 1,
            name: "Servicio",
            quantity: 1,
            unit_price: 10000,
            total_price: 10000,
          },
        ],
        total_clp: 10000,
        observations: "Nota",
        validity_days: 30,
        delivery_term_days: 5,
        files: [],
      },
    };

    const parsed = BridgeConfirmPostulationMessageSchema.safeParse(msg);
    expect(parsed.success).toBe(true);
  });

  it("valida mensaje FOCUS_POSTULATION_TAB del bridge", () => {
    const msg = {
      target: "CHIRIPA_EXTENSION",
      type: "FOCUS_POSTULATION_TAB",
      nonce: "c9d64a2f-e8b9-4674-8b01-526bfd283669",
      payload: {
        tender_code: "2499-12-L126",
      },
    };

    const parsed = BridgeFocusTabMessageSchema.safeParse(msg);
    expect(parsed.success).toBe(true);
  });
});
